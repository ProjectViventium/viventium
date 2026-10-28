from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import types
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "viventium" / "remote_call_tunnel.py"


def load_module(*, native_dns=False):
    spec = importlib.util.spec_from_file_location("remote_call_tunnel", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    if not native_dns:
        # Existing lifecycle tests must never query real DNS.
        module.resolve_public_ipv4_hosts = lambda hosts: {
            host: {"addresses": ["198.51.100.20"]} for host in hosts
        }
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
            "public_url": "https://voice-node.example.test",
        },
        "api": {
            "target": "http://localhost:3180",
            "public_url": "https://voice-node.example.test:8443",
        },
        "public_client_url": "https://voice-node.example.test",
        "public_api_url": "https://voice-node.example.test:8443",
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
        "-e",
        "Viventium public HTTPS",
        "-a",
        "10.0.0.2",
        "64823",
        "443",
        "TCP",
        "7200",
    ]]


def test_ensure_upnp_mapping_reclaims_dead_same_host_conflict(monkeypatch) -> None:
    module = load_module()
    events: list[tuple[str, int | list[str]]] = []

    monkeypatch.setattr(
        module,
        "list_upnpc_state",
        lambda _bin: {"mappings": {("TCP", 80): ("10.0.0.2", 50779)}},
    )
    monkeypatch.setattr(module, "mapping_target_reachable", lambda host, port, **_kwargs: False)
    monkeypatch.setattr(
        module,
        "remove_upnp_mapping",
        lambda _bin, *, external_port, protocol: events.append(("remove", external_port)),
    )

    def fake_run_checked(command: list[str], **_kwargs):
        events.append(("add", command))
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(module, "run_checked", fake_run_checked)

    module.ensure_upnp_mapping(
        "/opt/homebrew/bin/upnpc",
        protocol="TCP",
        external_port=80,
        internal_host="10.0.0.2",
        internal_port=4080,
        description="Viventium public HTTP",
        lease_seconds=7200,
    )

    assert events == [
        ("remove", 80),
        (
            "add",
            [
                "/opt/homebrew/bin/upnpc",
                "-e",
                "Viventium public HTTP",
                "-a",
                "10.0.0.2",
                "4080",
                "80",
                "TCP",
                "7200",
            ],
        ),
    ]


def test_ensure_upnp_mapping_preserves_active_conflict(monkeypatch) -> None:
    module = load_module()

    monkeypatch.setattr(
        module,
        "list_upnpc_state",
        lambda _bin: {"mappings": {("TCP", 80): ("10.0.0.2", 50779)}},
    )
    monkeypatch.setattr(module, "mapping_target_reachable", lambda host, port, **_kwargs: True)

    with pytest.raises(RuntimeError, match=r"Router already forwards TCP 80 to 10\.0\.0\.2:50779"):
        module.ensure_upnp_mapping(
            "/opt/homebrew/bin/upnpc",
            protocol="TCP",
            external_port=80,
            internal_host="10.0.0.2",
            internal_port=4080,
            description="Viventium public HTTP",
            lease_seconds=7200,
        )


def test_ensure_upnp_mapping_rejects_foreign_host_conflict(monkeypatch) -> None:
    module = load_module()

    monkeypatch.setattr(
        module,
        "list_upnpc_state",
        lambda _bin: {"mappings": {("TCP", 80): ("10.0.0.99", 50779)}},
    )

    with pytest.raises(RuntimeError, match=r"Router already forwards TCP 80 to 10\.0\.0\.99:50779"):
        module.ensure_upnp_mapping(
            "/opt/homebrew/bin/upnpc",
            protocol="TCP",
            external_port=80,
            internal_host="10.0.0.2",
            internal_port=4080,
            description="Viventium public HTTP",
            lease_seconds=7200,
        )


def test_tailscale_state_ready_requires_matching_dns_name(monkeypatch) -> None:
    module = load_module()

    monkeypatch.setattr(module, "resolve_binary", lambda _name: "/opt/homebrew/bin/tailscale")
    monkeypatch.setattr(module, "probe_local_endpoint", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        module,
        "tailscale_status_json",
        lambda _bin: {"Self": {"DNSName": "voice-node.example.test."}},
    )

    assert (
        module.tailscale_state_ready(
                {
                    "provider": "tailscale_tailnet_https",
                    "client": {"target": "http://localhost:3190", "public_url": "https://x"},
                    "tailscale": {"dns_name": "other-node.example.test", "managed_ports": [443]},
                    "public_client_url": "https://voice-node.example.test",
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


def test_public_https_edge_state_rebuilds_when_livekit_node_ip_contract_changes(
    monkeypatch,
) -> None:
    module = load_module()

    monkeypatch.setattr(module, "assigned_local_ipv4s", lambda: {"192.168.50.10"})

    args = types.SimpleNamespace(livekit_node_ip="")
    state = {
        "provider": "public_https_edge",
        "livekit_node_ip": "203.0.113.42",
        "router": {"local_ip": "192.168.50.10"},
    }

    assert module.state_matches_requested_livekit_node_ip("public_https_edge", args, state) is False

    state["livekit_node_ip"] = "192.168.50.10"
    assert module.state_matches_requested_livekit_node_ip("public_https_edge", args, state) is True

    args.livekit_node_ip = "198.51.100.24"
    assert module.state_matches_requested_livekit_node_ip("public_https_edge", args, state) is False

    state["livekit_node_ip"] = "198.51.100.24"
    assert module.state_matches_requested_livekit_node_ip("public_https_edge", args, state) is True


def test_public_https_edge_state_rejects_self_consistent_stale_livekit_node_ip(
    monkeypatch,
) -> None:
    module = load_module()

    args = types.SimpleNamespace(livekit_node_ip="")
    state = {
        "provider": "public_https_edge",
        "livekit_node_ip": "192.168.50.10",
        "router": {"local_ip": "192.168.50.10"},
    }

    monkeypatch.setattr(module, "assigned_local_ipv4s", lambda: {"192.168.60.10"})
    monkeypatch.setattr(module, "detect_lan_ipv4", lambda: "192.168.60.10")

    assert module.state_matches_requested_livekit_node_ip("public_https_edge", args, state) is False

    state["livekit_node_ip"] = "192.168.60.10"
    state["router"]["local_ip"] = "192.168.60.10"
    assert module.state_matches_requested_livekit_node_ip("public_https_edge", args, state) is True


def test_public_https_edge_state_allows_assigned_non_default_livekit_node_ip(
    monkeypatch,
) -> None:
    module = load_module()

    args = types.SimpleNamespace(livekit_node_ip="")
    state = {
        "provider": "public_https_edge",
        "livekit_node_ip": "192.168.50.10",
        "router": {"local_ip": "192.168.50.10"},
    }

    monkeypatch.setattr(module, "assigned_local_ipv4s", lambda: {"192.168.60.10", "192.168.50.10"})
    monkeypatch.setattr(module, "detect_lan_ipv4", lambda: "192.168.60.10")

    assert module.state_matches_requested_livekit_node_ip("public_https_edge", args, state) is True


def test_public_https_edge_state_preserves_explicit_livekit_node_ip_override(
    monkeypatch,
) -> None:
    module = load_module()

    monkeypatch.setattr(module, "assigned_local_ipv4s", lambda: {"192.168.50.10"})
    monkeypatch.setattr(module, "detect_lan_ipv4", lambda: "192.168.50.10")

    args = types.SimpleNamespace(livekit_node_ip="100.64.0.12")
    state = {
        "provider": "public_https_edge",
        "livekit_node_ip": "100.64.0.12",
        "router": {"local_ip": "192.168.50.10"},
    }

    assert module.state_matches_requested_livekit_node_ip("public_https_edge", args, state) is True


def test_public_https_edge_state_handles_missing_router_local_ip(monkeypatch) -> None:
    module = load_module()

    args = types.SimpleNamespace(livekit_node_ip="")
    state = {
        "provider": "public_https_edge",
        "livekit_node_ip": "192.168.50.10",
    }

    monkeypatch.setattr(module, "assigned_local_ipv4s", lambda: {"192.168.50.10"})
    assert module.state_matches_requested_livekit_node_ip("public_https_edge", args, state) is True

    monkeypatch.setattr(module, "assigned_local_ipv4s", lambda: {"192.168.60.10"})
    assert module.state_matches_requested_livekit_node_ip("public_https_edge", args, state) is False


def test_livekit_node_ip_state_validation_is_scoped_to_public_https_edge() -> None:
    module = load_module()

    args = types.SimpleNamespace(livekit_node_ip="")
    state = {
        "provider": "cloudflare_quick_tunnel",
        "livekit_node_ip": "203.0.113.42",
        "router": {"local_ip": "192.168.50.10"},
    }

    for provider in ("cloudflare_quick_tunnel", "tailscale_tailnet_https", "netbird_selfhosted_mesh"):
        assert module.state_matches_requested_livekit_node_ip(provider, args, state) is True


def test_assigned_local_ipv4s_parses_macos_ifconfig_and_filters_special_ranges(
    monkeypatch,
) -> None:
    module = load_module()
    commands: list[list[str]] = []

    monkeypatch.setattr(module.socket, "gethostname", lambda: "viventium-test")
    monkeypatch.setattr(module.socket, "getfqdn", lambda: "viventium-test.local")
    monkeypatch.setattr(module.socket, "getaddrinfo", lambda *_args, **_kwargs: [])

    def fake_run_checked(command: list[str], **_kwargs):
        commands.append(command)
        return types.SimpleNamespace(
            returncode=0,
            stdout="""
lo0: flags=8049<UP,LOOPBACK,RUNNING,MULTICAST> mtu 16384
    inet 127.0.0.1 netmask 0xff000000
en0: flags=8863<UP,BROADCAST,RUNNING,SIMPLEX,MULTICAST> mtu 1500
    inet6 fe80::1%en0 prefixlen 64 secured scopeid 0x6
    inet 169.254.10.5 netmask 0xffff0000 broadcast 169.254.255.255
    inet 192.168.50.10 netmask 0xffffff00 broadcast 192.168.50.255
""",
        )

    monkeypatch.setattr(module, "run_checked", fake_run_checked)

    assert module.assigned_local_ipv4s() == {"192.168.50.10"}
    assert commands == [["ifconfig"]]


def test_assigned_local_ipv4s_falls_back_to_linux_ip_output(monkeypatch) -> None:
    module = load_module()
    commands: list[list[str]] = []

    monkeypatch.setattr(module.socket, "gethostname", lambda: "viventium-test")
    monkeypatch.setattr(module.socket, "getfqdn", lambda: "viventium-test.local")
    monkeypatch.setattr(module.socket, "getaddrinfo", lambda *_args, **_kwargs: [])

    def fake_run_checked(command: list[str], **_kwargs):
        commands.append(command)
        if command == ["ifconfig"]:
            return types.SimpleNamespace(returncode=0, stdout="")
        return types.SimpleNamespace(
            returncode=0,
            stdout="""
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.60.10/24 brd 192.168.60.255 scope global eth0
    inet6 fe80::1/64 scope link
""",
        )

    monkeypatch.setattr(module, "run_checked", fake_run_checked)

    assert module.assigned_local_ipv4s() == {"192.168.60.10"}
    assert commands == [["ifconfig"], ["ip", "-4", "addr", "show"]]


def test_assigned_local_ipv4s_uses_getaddrinfo_when_interface_commands_fail(
    monkeypatch,
) -> None:
    module = load_module()

    monkeypatch.setattr(module.socket, "gethostname", lambda: "viventium-test")
    monkeypatch.setattr(module.socket, "getfqdn", lambda: "viventium-test.local")
    monkeypatch.setattr(
        module.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (module.socket.AF_INET, None, None, None, ("127.0.0.1", 0)),
            (module.socket.AF_INET, None, None, None, ("192.168.70.10", 0)),
        ],
    )
    monkeypatch.setattr(module, "run_checked", lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError()))

    assert module.assigned_local_ipv4s() == {"192.168.70.10"}


def test_cmd_start_public_https_edge_rebuilds_stale_livekit_node_ip_state(
    monkeypatch, tmp_path: Path
) -> None:
    module = load_module()

    class DummyLock:
        def fileno(self):
            return 0

        def close(self):
            return None

    stale_state = {
        "provider": "public_https_edge",
        "livekit_node_ip": "192.168.50.10",
        "router": {"local_ip": "192.168.50.10"},
        "caddy": {"pid": 777},
        "client": {"target": "http://127.0.0.1:3190", "public_url": "https://app.example.test"},
    }
    rebuilt_state = {
        "provider": "public_https_edge",
        "livekit_node_ip": "192.168.60.10",
        "router": {"local_ip": "192.168.60.10"},
        "caddy": {"pid": 888},
        "client": {"target": "http://127.0.0.1:3190", "public_url": "https://app.example.test"},
    }
    stopped: list[dict[str, object]] = []
    saved: dict[str, object] = {}
    starts: list[object] = []

    monkeypatch.setattr(module, "with_lock", lambda _path: DummyLock())
    monkeypatch.setattr(module.fcntl, "flock", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "load_state", lambda _path: dict(stale_state))
    monkeypatch.setattr(module, "stop_state", lambda state: stopped.append(dict(state)))
    monkeypatch.setattr(module, "state_is_healthy", lambda state: bool(state))
    monkeypatch.setattr(module, "assigned_local_ipv4s", lambda: {"192.168.60.10"})
    monkeypatch.setattr(module, "detect_lan_ipv4", lambda: "192.168.60.10")
    monkeypatch.setattr(
        module,
        "start_public_https_edge",
        lambda args, *, state_path, log_dir: starts.append(args) or dict(rebuilt_state),
    )
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

    assert stopped == [stale_state]
    assert len(starts) == 1
    assert saved["livekit_node_ip"] == "192.168.60.10"


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
    monkeypatch.setattr(module, "list_upnpc_state", lambda _bin: {"local_ip": "192.168.50.10"})
    monkeypatch.setattr(module, "assigned_local_ipv4s", lambda: {"192.168.50.10"})
    monkeypatch.setattr(module.time, "strftime", lambda *_args, **_kwargs: "2026-04-07T03:30:00Z")

    monkeypatch.setattr(
        module,
        "ensure_upnp_mapping",
        lambda _bin, *, protocol, external_port, internal_host, internal_port, description, lease_seconds=14400, previous_internal_host="", renew_existing=False: captured.append(
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
    monkeypatch.setattr(module, "tailscale_status_json", lambda _bin: {"Self": {"DNSName": "voice-node.example.test."}})
    monkeypatch.setattr(module, "tailscale_dns_name", lambda _status: "voice-node.example.test")
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
    assert saved["public_client_url"] == "https://voice-node.example.test"
    assert saved["public_api_url"] == "https://voice-node.example.test:8443"
    assert saved["public_playground_url"] == "https://voice-node.example.test:3443"
    assert saved["public_livekit_url"] == "wss://voice-node.example.test:7443"
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
        glasshive_port=8780,
        livekit_tcp_port=7889,
        livekit_udp_port=7890,
        livekit_turn_tls_port=5349,
        public_client_origin="",
        public_api_origin="",
        public_playground_origin="",
        public_livekit_url="",
        public_glasshive_origin="",
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
                "glasshive.203.0.113.42.sslip.io",
            ],
            4443,
            5,
        )
    ]
    assert saved["public_client_url"] == "https://app.203.0.113.42.sslip.io"
    assert saved["public_api_url"] == "https://api.203.0.113.42.sslip.io"
    assert saved["public_playground_url"] == "https://playground.203.0.113.42.sslip.io"
    assert saved["public_livekit_url"] == "wss://livekit.203.0.113.42.sslip.io"
    assert saved["public_glasshive_url"] == "https://glasshive.203.0.113.42.sslip.io"
    assert saved["livekit_node_ip"] == "192.168.50.10"
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
    assert "glasshive.203.0.113.42.sslip.io" in written_configs[config_path]
    assert "reverse_proxy 127.0.0.1:8780" in written_configs[config_path]
    assert saved["livekit_turn_domain"] == "livekit.203.0.113.42.sslip.io"
    assert saved["livekit_turn_tls_port"] == 5349
    assert saved["livekit_turn_cert_file"] == "/tmp/livekit-turn.crt"
    assert saved["livekit_turn_key_file"] == "/tmp/livekit-turn.key"


def test_public_https_edge_rebuilds_when_requested_glasshive_surface_is_missing() -> None:
    module = load_module()
    args = types.SimpleNamespace(
        client_port=3190,
        api_port=3180,
        playground_port=3300,
        livekit_port=7888,
        glasshive_port=8780,
        public_client_origin="https://app.example.test",
        public_api_origin="https://api.app.example.test",
        public_playground_origin="https://playground.app.example.test",
        public_livekit_url="wss://livekit.app.example.test",
        public_glasshive_origin="https://glasshive.app.example.test",
    )
    state = {
        "provider": "public_https_edge",
        "client": {"target": "http://localhost:3190", "public_url": "https://app.example.test"},
        "api": {"target": "http://localhost:3180", "public_url": "https://api.app.example.test"},
        "playground": {
            "target": "http://localhost:3300",
            "public_url": "https://playground.app.example.test",
        },
        "livekit": {
            "target": "http://localhost:7888",
            "public_url": "https://livekit.app.example.test",
            "public_ws_url": "wss://livekit.app.example.test",
        },
    }

    assert module.state_matches_requested_public_edge_surfaces(args, state) is False


@pytest.mark.parametrize(("node_ip", "wan_ip", "api_host"), [
    ("198.51.100.24", "203.0.113.42", ""),
    ("8.8.8.8", "8.8.8.8", ""),
    ("192.168.50.10", "9.9.9.9", ""),
    ("8.8.8.8", "9.9.9.9", "https://media.example.test"),
    ("8.8.8.8", "9.9.9.9", "http://localhost:9999"),
])
def test_cmd_start_public_https_edge_preserves_explicit_livekit_node_ip(monkeypatch, tmp_path: Path, node_ip, wan_ip, api_host) -> None:
    module = load_module()
    monkeypatch.setenv("LIVEKIT_API_HOST", api_host)
    monkeypatch.setattr(module, "assigned_local_ipv4s", lambda: {"192.168.50.10"})

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
        lambda _bin: {"external_ip": wan_ip, "local_ip": "192.168.50.10", "mappings": {}},
    )
    monkeypatch.setattr(module, "discover_public_ipv4", lambda _bin=None: wan_ip)
    monkeypatch.setattr(module, "pick_caddy_admin_port", lambda: 2019)
    ports = iter([4080, 4443])
    monkeypatch.setattr(module, "pick_free_port", lambda: next(ports))
    monkeypatch.setattr(module, "ensure_upnp_mapping", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "start_caddy_process", lambda *_args, **_kwargs: 777)
    monkeypatch.setattr(
        module,
        "wait_for_public_caddy_hosts",
        lambda _hostnames, *, https_port, timeout_seconds: None,
    )
    monkeypatch.setattr(module, "resolve_public_edge_livekit_cert_pair", lambda *_args: ("", ""))
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
        livekit_node_ip=node_ip,
        caddy_data_dir="",
        provider="public_https_edge",
        auto_install=False,
        timeout_seconds=5,
        command="start",
    )

    assert module.cmd_start(args) == 0

    assert saved["livekit_node_ip"] == node_ip


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
        raise RuntimeError("Router already forwards TCP 80 to 192.0.2.44:50779")

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


def test_render_caddyfile_redacts_opaque_glasshive_refs_from_runtime_errors() -> None:
    module = load_module()

    caddyfile = module.render_caddyfile(
        admin_port=2019,
        surfaces=[("glasshive.example.com", 8780)],
        tls_internal=False,
        http_port=4080,
        https_port=4443,
    )

    assert "request>uri regexp" in caddyfile
    assert "(?:r|v1/link-refs)" in caddyfile
    assert "request>headers>Referer delete" in caddyfile


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


# Native public-edge refresh regressions: synthetic addresses and router only.
def edge_refresh_fixture(module, monkeypatch, *, moved=True):
    import copy
    old_ip, new_ip = "192.0.2.10", "192.0.2.11" if moved else "192.0.2.10"
    ports = [("TCP", 80, 45080), ("TCP", 443, 45443), ("TCP", 7889, 7889), ("UDP", 7890, 7890), ("TCP", 5349, 5349)]
    state = {
        "provider": "public_https_edge", "public_ip": "198.51.100.20", "livekit_node_ip": "198.51.100.20",
        "public_playground_url": "https://voice.example.test", "public_livekit_url": "wss://media.example.test",
        "caddy": {"pid": 701, "http_port": 45080, "https_port": 45443},
        "router": {"local_ip": old_ip, "mappings": [
            {"protocol": proto, "external_port": external, "internal_host": old_ip, "internal_port": internal}
            for proto, external, internal in ports
        ]},
    }
    live = {"local_ip": new_ip, "external_ip": state["public_ip"], "mappings": {
        (proto, external): (old_ip, internal) for proto, external, internal in ports
    }, "mapping_descriptions": {(proto, external): module.public_edge_mapping_description(proto, external)
                                 for proto, external, _internal in ports}}
    commands = []
    monkeypatch.setattr(module, "resolve_binary", lambda _name: "/synthetic/upnpc")
    monkeypatch.setattr(module, "list_upnpc_state", lambda _bin: copy.deepcopy(live))
    monkeypatch.setattr(module, "assigned_local_ipv4s", lambda: {new_ip})
    monkeypatch.setattr(module, "pid_is_running", lambda pid: pid == 701)
    monkeypatch.setattr(module, "mapping_target_reachable", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(module, "stop_state", lambda *_args: pytest.fail("Refresh must not stop the proxy"))
    def run(command, **_kwargs):
        commands.append(command)
        if "-d" in command:
            i = command.index("-d"); key = (command[i + 2], int(command[i + 1]))
            live["mappings"].pop(key, None); live["mapping_descriptions"].pop(key, None)
        elif "-a" in command:
            i = command.index("-a"); host, internal, external, proto = command[i + 1:i + 5]
            key = (proto, int(external))
            previous = live["mappings"].get(key)
            if previous and previous[0] != host:
                return types.SimpleNamespace(returncode=2, stdout="AddPortMapping() returned 718", stderr="")
            live["mappings"][key] = (host, int(internal))
            live["mapping_descriptions"][key] = command[command.index("-e") + 1]
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(module, "run_checked", run)
    return state, live, commands, ports, old_ip, new_ip


def test_refresh_owned_dhcp_drift_moves_exact_ports_without_stopping_proxy(monkeypatch):
    import copy
    module = load_module()
    state, live, commands, ports, old_ip, new_ip = edge_refresh_fixture(module, monkeypatch)
    original = copy.deepcopy(state)
    result = module.refresh_public_https_edge_mappings(state, lease_seconds=14400)
    assert len(commands) == 10
    for n, (proto, external, internal) in enumerate(ports):
        assert commands[2 * n] == ["/synthetic/upnpc", "-d", str(external), proto]
        assert commands[2 * n + 1] == ["/synthetic/upnpc", "-e", module.public_edge_mapping_description(proto, external),
                                     "-a", new_ip, str(internal), str(external), proto, "14400"]
    assert state == original
    assert result["router"]["local_ip"] == new_ip
    assert all(m["internal_host"] == new_ip for m in result["router"]["mappings"])
    assert result["caddy"] == original["caddy"]
    assert {k: v for k, v in result.items() if k != "router"} == {k: v for k, v in original.items() if k != "router"}
    assert live["mappings"] == {(proto, external): (new_ip, internal) for proto, external, internal in ports}


def test_refresh_matching_owned_mappings_actually_renews_router_leases(monkeypatch):
    module = load_module()
    state, _live, commands, ports, _old_ip, new_ip = edge_refresh_fixture(module, monkeypatch, moved=False)
    result = module.refresh_public_https_edge_mappings(state, lease_seconds=14400)
    assert commands == [["/synthetic/upnpc", "-e", module.public_edge_mapping_description(proto, external),
                         "-a", new_ip, str(internal), str(external), proto, "14400"] for proto, external, internal in ports]
    assert result["router"]["mapping_lease_seconds"] == 14400


def test_refresh_dhcp_partial_retry_renews_moved_key_without_deleting_it(monkeypatch):
    module = load_module()
    state, live, commands, _ports, _old_ip, new_ip = edge_refresh_fixture(module, monkeypatch)
    live["mappings"][("TCP", 80)] = (new_ip, 45080)
    result = module.refresh_public_https_edge_mappings(state, lease_seconds=14400)
    assert len(commands) == 9
    assert "-a" in commands[0] and "-d" not in commands[0]
    assert all(m["internal_host"] == new_ip for m in result["router"]["mappings"])


@pytest.mark.parametrize("fault", ["foreign_target", "foreign_description", "wan_changed", "current_unassigned", "old_still_assigned", "missing_local", "missing_old", "dead_proxy", "edge_port_changed", "invalid_protocol", "previous_target_active"])
def test_refresh_dhcp_identity_faults_fail_before_any_router_write(monkeypatch, fault):
    module = load_module()
    state, live, commands, _ports, old_ip, new_ip = edge_refresh_fixture(module, monkeypatch)
    if fault == "foreign_target": live["mappings"][("TCP", 443)] = ("192.0.2.99", 45443)
    elif fault == "foreign_description": live["mapping_descriptions"][("TCP", 443)] = "Other application"
    elif fault == "wan_changed": live["external_ip"] = "198.51.100.21"
    elif fault == "current_unassigned": monkeypatch.setattr(module, "assigned_local_ipv4s", lambda: {"192.0.2.12"})
    elif fault == "old_still_assigned": monkeypatch.setattr(module, "assigned_local_ipv4s", lambda: {old_ip, new_ip})
    elif fault == "missing_local": live["local_ip"] = ""
    elif fault == "missing_old": state["router"]["local_ip"] = ""
    elif fault == "dead_proxy": monkeypatch.setattr(module, "pid_is_running", lambda _pid: False)
    elif fault == "edge_port_changed": state["caddy"]["https_port"] = 45444
    elif fault == "invalid_protocol": state["router"]["mappings"][0]["protocol"] = "SCTP"
    elif fault == "previous_target_active": monkeypatch.setattr(module, "mapping_target_reachable", lambda *_args, **_kwargs: True)
    with pytest.raises(RuntimeError): module.refresh_public_https_edge_mappings(state, lease_seconds=14400)
    assert commands == []


def test_refresh_owned_tuple_description_replacement_does_not_renew_foreign_mapping(monkeypatch):
    module = load_module()
    state, live, commands, _ports, _old_ip, _new_ip = edge_refresh_fixture(module, monkeypatch, moved=False)
    live["mapping_descriptions"][("TCP", 80)] = "Other application"
    with pytest.raises(RuntimeError): module.refresh_public_https_edge_mappings(state, lease_seconds=14400)
    assert commands == []


def test_refresh_router_add_failure_does_not_report_saved_success_or_stop_proxy(monkeypatch):
    import copy
    module = load_module()
    state, _live, commands, _ports, _old_ip, _new_ip = edge_refresh_fixture(module, monkeypatch)
    original = copy.deepcopy(state)
    actual_run = module.run_checked
    def fail_add(command, **kwargs):
        if "-a" in command:
            commands.append(command)
            return types.SimpleNamespace(returncode=2, stdout="AddPortMapping() returned 501", stderr="")
        return actual_run(command, **kwargs)
    monkeypatch.setattr(module, "run_checked", fail_add)
    with pytest.raises(RuntimeError, match="Failed to create router port forward"):
        module.refresh_public_https_edge_mappings(state, lease_seconds=14400)
    assert len(commands) == 2 and "-d" in commands[0] and "-a" in commands[1]
    assert state == original


def test_public_edge_health_rejects_saved_unassigned_lan_without_rewriting_media_node(monkeypatch):
    module = load_module()
    state, _live, _commands, _ports, _old_ip, _new_ip = edge_refresh_fixture(module, monkeypatch)
    state["client"] = {"target": "http://127.0.0.1:3190", "public_url": "https://app.example.test"}
    monkeypatch.setattr(module, "probe_local_endpoint", lambda *_args, **_kwargs: True)
    assert module.state_is_healthy(state) is False
    assert state["livekit_node_ip"] == "198.51.100.20"


def test_parse_upnpc_retains_native_mapping_descriptions_for_exact_ownership():
    module = load_module()
    parsed = module.parse_upnpc_listing("Local LAN ip address : 192.0.2.10\nExternalIPAddress = 198.51.100.20\n 0 TCP 443->192.0.2.10:45443 'Viventium public HTTPS' '' 3739\n")
    assert parsed["mappings"][("TCP", 443)] == ("192.0.2.10", 45443)
    assert parsed["mapping_descriptions"][("TCP", 443)] == "Viventium public HTTPS"


def test_cmd_refresh_lock_covers_read_router_changes_and_state_save(monkeypatch, tmp_path):
    module = load_module()
    held = [False]
    class Lock:
        def fileno(self): return 82
        def close(self): assert held[0] is False
    def lock(path):
        assert path == tmp_path / "edge.lock"
        held[0] = True
        return Lock()
    def load(_path):
        assert held[0] is True
        return {"provider": "public_https_edge"}
    def refresh(state, *, lease_seconds):
        assert held[0] is True and lease_seconds == 14400
        return state
    def save(_path, _state): assert held[0] is True
    def unlock(_fd, mode):
        assert mode == module.fcntl.LOCK_UN
        held[0] = False
    monkeypatch.setattr(module, "with_lock", lock)
    monkeypatch.setattr(module, "load_state", load)
    monkeypatch.setattr(module, "refresh_public_https_edge_mappings", refresh)
    monkeypatch.setattr(module, "save_state", save)
    monkeypatch.setattr(module.fcntl, "flock", unlock)
    assert module.cmd_refresh_mappings(types.SimpleNamespace(state_file=str(tmp_path / "edge.json"), upnp_lease_seconds=14400)) == 0
    assert held[0] is False



def test_refresh_failed_dhcp_add_retry_restores_exact_missing_owned_key(monkeypatch):
    module = load_module()
    state, live, commands, ports, _old_ip, new_ip = edge_refresh_fixture(module, monkeypatch)
    actual_run = module.run_checked
    def fail_add(command, **kwargs):
        if "-a" in command:
            commands.append(command)
            return types.SimpleNamespace(returncode=2, stdout="AddPortMapping() returned 501", stderr="")
        return actual_run(command, **kwargs)
    monkeypatch.setattr(module, "run_checked", fail_add)
    with pytest.raises(RuntimeError): module.refresh_public_https_edge_mappings(state, lease_seconds=14400)
    assert ("TCP", 80) not in live["mappings"]
    commands.clear()
    monkeypatch.setattr(module, "run_checked", actual_run)
    result = module.refresh_public_https_edge_mappings(state, lease_seconds=14400)
    assert len(commands) == 9 and "-a" in commands[0]
    assert live["mappings"] == {(proto, external): (new_ip, internal) for proto, external, internal in ports}
    assert all(mapping["internal_host"] == new_ip for mapping in result["router"]["mappings"])


@pytest.mark.parametrize("moved", [False, True])
@pytest.mark.parametrize("wan", ["198.51.100.21", "", None])
def test_refresh_wan_drift_fails_before_router_writes_and_preserves_owned_state(monkeypatch, moved, wan):
    import copy
    module = load_module()
    state, live, commands, _ports, _old_ip, _new_ip = edge_refresh_fixture(module, monkeypatch, moved=moved)
    original = copy.deepcopy(state)
    live["external_ip"] = wan
    if wan is None:
        monkeypatch.setattr(module, "list_upnpc_state", lambda _bin: (_ for _ in ()).throw(RuntimeError("Router unavailable")))
    with pytest.raises(module.PublicEdgeWanError) as error:
        module.refresh_public_https_edge_mappings(state, lease_seconds=14400)
    assert error.value.code == ("public_edge_wan_changed" if wan else "public_edge_wan_unavailable")
    assert commands == []
    assert state == original


def test_cmd_refresh_wan_error_persists_full_state_status_and_stop_ownership(monkeypatch, tmp_path, capsys):
    import copy
    module = load_module()
    state, live, commands, _ports, _old_ip, _new_ip = edge_refresh_fixture(module, monkeypatch, moved=False)
    state["client"] = {"target": "http://127.0.0.1:3190", "public_url": "https://app.example.test"}
    state_path = tmp_path / "edge.json"
    module.save_state(state_path, state)
    original = copy.deepcopy(state)
    live["external_ip"] = "198.51.100.21"
    args = types.SimpleNamespace(state_file=str(state_path), upnp_lease_seconds=14400)
    with pytest.raises(module.PublicEdgeWanError):
        module.cmd_refresh_mappings(args)
    failed = module.load_state(state_path)
    assert failed["last_error_code"] == "public_edge_wan_changed"
    assert "Update public DNS" in failed["last_error"]
    assert {key: value for key, value in failed.items() if key not in {"last_error", "last_error_code"}} == original
    assert commands == []
    assert module.cmd_status(args) == 1
    assert json.loads(capsys.readouterr().out)["healthy"] is False
    stopped = []
    monkeypatch.setattr(module, "stop_state", lambda saved: stopped.append(saved))
    assert module.cmd_stop(args) == 0
    assert stopped == [failed]
    assert not state_path.exists()


def test_cmd_start_does_not_retire_edge_with_unresolved_wan_error(monkeypatch, tmp_path):
    module = load_module()
    state, _live, commands, _ports, _old_ip, _new_ip = edge_refresh_fixture(module, monkeypatch, moved=False)
    state.update(last_error_code="public_edge_wan_changed", last_error="Update public DNS and restart")
    state_path = tmp_path / "edge.json"
    module.save_state(state_path, state)
    monkeypatch.setattr(module, "start_public_https_edge", lambda *_args, **_kwargs: pytest.fail("Must preserve unresolved edge"))
    args = types.SimpleNamespace(state_file=str(state_path), log_dir=str(tmp_path / "logs"), provider="public_https_edge")
    with pytest.raises(RuntimeError, match="Update public DNS"):
        module.cmd_start(args)
    assert module.load_state(state_path) == state
    assert commands == []


@pytest.mark.parametrize("local_healthy", [False, True])
def test_cmd_start_checks_current_wan_before_reusing_or_retiring_owned_edge(monkeypatch, tmp_path, local_healthy):
    module = load_module()
    state, live, commands, _ports, _old_ip, _new_ip = edge_refresh_fixture(module, monkeypatch, moved=False)
    live["external_ip"] = "198.51.100.21"
    state_path = tmp_path / "edge.json"
    module.save_state(state_path, state)
    monkeypatch.setattr(module, "state_is_healthy", lambda _state: local_healthy)
    args = types.SimpleNamespace(state_file=str(state_path), log_dir=str(tmp_path / "logs"), provider="public_https_edge")
    with pytest.raises(module.PublicEdgeWanError): module.cmd_start(args)
    retained = module.load_state(state_path)
    assert retained["last_error_code"] == "public_edge_wan_changed"
    assert retained["caddy"] == state["caddy"] and retained["router"] == state["router"]
    assert commands == []


@pytest.mark.parametrize("fault", ["none", "local_target_down", "dead_caddy", "unknown_wan", "missing_saved_wan", "mapping_rejected", "unrelated_error"])
def test_wan_error_clears_only_after_verified_address_mapping_and_local_recovery(monkeypatch, tmp_path, fault):
    module = load_module()
    state, live, _commands, _ports, _old_ip, _new_ip = edge_refresh_fixture(module, monkeypatch, moved=False)
    state["client"] = {"target": "http://127.0.0.1:3190", "public_url": "https://app.example.test"}
    state.update(last_error_code="public_edge_wan_changed", last_error="Update public DNS and restart")
    monkeypatch.setattr(module, "probe_local_endpoint", lambda *_args, **_kwargs: fault != "local_target_down")
    if fault == "dead_caddy": monkeypatch.setattr(module, "pid_is_running", lambda _pid: False)
    elif fault == "unknown_wan": live["external_ip"] = ""
    elif fault == "missing_saved_wan": state["public_ip"] = ""
    elif fault == "mapping_rejected":
        monkeypatch.setattr(module, "ensure_upnp_mapping", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("Router rejected renewal")))
    elif fault == "unrelated_error": state.update(last_error_code="another_error", last_error="Another failure")
    state_path = tmp_path / "edge.json"
    module.save_state(state_path, state)
    args = types.SimpleNamespace(state_file=str(state_path), upnp_lease_seconds=14400)
    if fault == "none":
        assert module.cmd_refresh_mappings(args) == 0
        recovered = module.load_state(state_path)
        assert "last_error" not in recovered and "last_error_code" not in recovered
        assert module.state_is_healthy(recovered) is True
        assert recovered["caddy"] == state["caddy"]
        assert recovered["router"]["mappings"] == state["router"]["mappings"]
    else:
        with pytest.raises(RuntimeError): module.cmd_refresh_mappings(args)
        retained = module.load_state(state_path)
        assert retained["last_error"]
        assert module.state_is_healthy(retained) is False


def healthy_edge_start_fixture(module, monkeypatch, tmp_path):
    state, live, commands, _ports, _old_ip, _new_ip = edge_refresh_fixture(module, monkeypatch, moved=False)
    state["client"] = {"target": module.surface_target_url(3190), "public_url": "https://app.example.test"}
    state_path = tmp_path / "edge.json"
    module.save_state(state_path, state)
    monkeypatch.setattr(module, "probe_local_endpoint", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(module, "start_public_https_edge", lambda *_args, **_kwargs: pytest.fail("Must reuse the existing edge"))
    args = types.SimpleNamespace(
        state_file=str(state_path), log_dir=str(tmp_path / "logs"), provider="public_https_edge",
        client_port=3190, api_port=0, playground_port=0, livekit_port=0, glasshive_port=0,
        livekit_node_ip=state["livekit_node_ip"], public_client_origin="https://app.example.test",
    )
    return state, live, commands, state_path, args


@pytest.mark.parametrize("observer", ["missing_binary", "router_unavailable", "router_wan_missing"])
@pytest.mark.parametrize("wan", ["198.51.100.20", "198.51.100.21", ""])
def test_start_observation_fallback_preserves_existing_edge_without_upnp_dependency(monkeypatch, tmp_path, observer, wan):
    module = load_module()
    state, live, commands, state_path, args = healthy_edge_start_fixture(module, monkeypatch, tmp_path)
    if observer == "missing_binary": monkeypatch.setattr(module, "resolve_binary", lambda _name: None)
    elif observer == "router_unavailable":
        monkeypatch.setattr(module, "list_upnpc_state", lambda _bin: (_ for _ in ()).throw(RuntimeError("Router unavailable")))
    else: live["external_ip"] = ""
    lookups = []
    def observe(upnpc_bin):
        lookups.append(upnpc_bin)
        if not wan: raise RuntimeError("Public address unavailable")
        return wan
    monkeypatch.setattr(module, "discover_public_ipv4", observe)
    if wan == state["public_ip"]:
        assert module.cmd_start(args) == 0
        assert {key: value for key, value in module.load_state(state_path).items() if key != "public_dns"} == state
    else:
        with pytest.raises(module.PublicEdgeWanError): module.cmd_start(args)
        retained = module.load_state(state_path)
        assert retained["last_error_code"] == ("public_edge_wan_changed" if wan else "public_edge_wan_unavailable")
        assert retained["caddy"] == state["caddy"] and retained["router"] == state["router"]
    assert lookups == [None]
    assert commands == []


def test_start_manual_forwarding_has_no_upnp_or_public_probe_dependency(monkeypatch, tmp_path):
    module = load_module()
    state, _live, commands, state_path, args = healthy_edge_start_fixture(module, monkeypatch, tmp_path)
    state["router"]["mappings"] = []
    module.save_state(state_path, state)
    monkeypatch.setattr(module, "resolve_binary", lambda _name: None)
    monkeypatch.setattr(module, "discover_public_ipv4", lambda *_args: pytest.fail("Manual edge reuse has no router observation dependency"))
    assert module.cmd_start(args) == 0
    assert {key: value for key, value in module.load_state(state_path).items() if key != "public_dns"} == state
    assert commands == []


@pytest.mark.parametrize("restored_by", ["router", "external_lookup", "local_target_down"])
def test_start_retry_recovers_transient_wan_observation_outage_without_teardown(monkeypatch, tmp_path, restored_by):
    module = load_module()
    state, _live, commands, state_path, args = healthy_edge_start_fixture(module, monkeypatch, tmp_path)
    router_observer = module.list_upnpc_state
    monkeypatch.setattr(module, "list_upnpc_state", lambda _bin: (_ for _ in ()).throw(RuntimeError("Router unavailable")))
    monkeypatch.setattr(module, "discover_public_ipv4", lambda _bin: (_ for _ in ()).throw(RuntimeError("Public address unavailable")))
    with pytest.raises(module.PublicEdgeWanError): module.cmd_start(args)
    failed = module.load_state(state_path)
    assert failed["last_error_code"] == "public_edge_wan_unavailable"
    assert module.state_is_healthy(failed) is False
    if restored_by != "external_lookup": monkeypatch.setattr(module, "list_upnpc_state", router_observer)
    else: monkeypatch.setattr(module, "discover_public_ipv4", lambda _bin: state["public_ip"])
    if restored_by == "local_target_down":
        monkeypatch.setattr(module, "probe_local_endpoint", lambda *_args, **_kwargs: False)
        with pytest.raises(RuntimeError): module.cmd_start(args)
        assert module.load_state(state_path) == failed
    else:
        assert module.cmd_start(args) == 0
        assert {key: value for key, value in module.load_state(state_path).items() if key != "public_dns"} == state
        assert module.state_is_healthy(state) is True
    assert commands == []


def test_start_observation_fallback_does_not_clear_recorded_wan_change(monkeypatch, tmp_path):
    module = load_module()
    state, _live, commands, state_path, args = healthy_edge_start_fixture(module, monkeypatch, tmp_path)
    state.update(last_error_code="public_edge_wan_changed", last_error="Update public DNS and restart")
    module.save_state(state_path, state)
    monkeypatch.setattr(module, "resolve_binary", lambda _name: None)
    monkeypatch.setattr(module, "discover_public_ipv4", lambda _bin: state["public_ip"])
    with pytest.raises(RuntimeError, match="Update public DNS"): module.cmd_start(args)
    assert module.load_state(state_path) == state
    assert commands == []


@pytest.mark.parametrize("moved", [False, True])
def test_mapping_refresh_never_substitutes_public_observation_for_router_ownership(monkeypatch, moved):
    module = load_module()
    state, _live, commands, _ports, _old_ip, _new_ip = edge_refresh_fixture(module, monkeypatch, moved=moved)
    monkeypatch.setattr(module, "list_upnpc_state", lambda _bin: (_ for _ in ()).throw(RuntimeError("Router unavailable")))
    monkeypatch.setattr(module, "discover_public_ipv4", lambda *_args: pytest.fail("Router writes need actual router evidence"))
    with pytest.raises(module.PublicEdgeWanError): module.refresh_public_https_edge_mappings(state, lease_seconds=14400)
    assert commands == []


@pytest.mark.parametrize("caller", ["start", "refresh"])
@pytest.mark.parametrize("unavailable", ["empty_wan", "router_error"])
def test_recorded_wan_change_survives_unknown_observation_and_same_ip_start_fallback(monkeypatch, tmp_path, caller, unavailable):
    module = load_module()
    state, live, commands, state_path, args = healthy_edge_start_fixture(module, monkeypatch, tmp_path)
    args.upnp_lease_seconds = 14400
    call = module.cmd_start if caller == "start" else module.cmd_refresh_mappings
    live["external_ip"] = "198.51.100.21"
    with pytest.raises(module.PublicEdgeWanError): call(args)
    changed = module.load_state(state_path)
    assert changed["last_error_code"] == "public_edge_wan_changed"
    live["external_ip"] = ""
    if unavailable == "router_error":
        monkeypatch.setattr(module, "list_upnpc_state", lambda _bin: (_ for _ in ()).throw(RuntimeError("Router unavailable")))
    monkeypatch.setattr(module, "discover_public_ipv4", lambda _bin: "")
    with pytest.raises(module.PublicEdgeWanError): call(args)
    assert module.load_state(state_path) == changed
    monkeypatch.setattr(module, "discover_public_ipv4", lambda _bin: state["public_ip"])
    with pytest.raises(RuntimeError, match="Update public DNS"): module.cmd_start(args)
    assert module.load_state(state_path) == changed
    assert changed["caddy"] == state["caddy"] and changed["router"] == state["router"]
    assert module.state_is_healthy(changed) is False
    assert commands == []


def test_fresh_local_public_media_mismatch_degrades_before_router_or_process_writes(monkeypatch, tmp_path):
    module = load_module()
    monkeypatch.delenv("LIVEKIT_API_HOST", raising=False)
    monkeypatch.setattr(module, "ensure_caddy", lambda _auto: "/synthetic/caddy")
    monkeypatch.setattr(module, "resolve_binary", lambda _name: "/synthetic/upnpc")
    monkeypatch.setattr(module, "list_upnpc_state", lambda _bin: {"local_ip": "192.0.2.10", "external_ip": "9.9.9.9"})
    monkeypatch.setattr(module, "discover_public_ipv4", lambda _bin: "9.9.9.9")
    monkeypatch.setattr(module, "assigned_local_ipv4s", lambda: {"192.0.2.10"})
    monkeypatch.setattr(module, "ensure_upnp_mapping", lambda *_args, **_kwargs: pytest.fail("Invalid media address must not create mappings"))
    monkeypatch.setattr(module, "start_caddy_process", lambda *_args, **_kwargs: pytest.fail("Invalid media address must not start Caddy"))
    state_path = tmp_path / "edge.json"
    args = types.SimpleNamespace(
        state_file=str(state_path), log_dir=str(tmp_path / "logs"), provider="public_https_edge", auto_install=False,
        client_port=3190, api_port=0, playground_port=0, livekit_port=7888, livekit_tcp_port=7889,
        livekit_udp_port=7890, livekit_node_ip="8.8.8.8",
    )
    with pytest.raises(module.PublicEdgeWanError, match="LiveKit media address"): module.cmd_start(args)
    failed = module.load_state(state_path)
    assert failed["last_error_code"] == "public_edge_wan_changed"
    assert module.state_is_healthy(failed) is False


@pytest.mark.parametrize("caller", ["start", "refresh"])
def test_saved_local_public_media_mismatch_degrades_without_retiring_owned_edge(monkeypatch, tmp_path, caller):
    module = load_module()
    state, live, commands, state_path, args = healthy_edge_start_fixture(module, monkeypatch, tmp_path)
    monkeypatch.delenv("LIVEKIT_API_HOST", raising=False)
    state.update(public_ip="9.9.9.9", livekit_node_ip="8.8.8.8")
    state["livekit"] = {"target": module.surface_target_url(7888), "public_ws_url": "wss://media.example.test"}
    live["external_ip"] = state["public_ip"]
    module.save_state(state_path, state)
    args.upnp_lease_seconds = 14400
    assert module.state_is_healthy(state) is False
    call = module.cmd_start if caller == "start" else module.cmd_refresh_mappings
    with pytest.raises(module.PublicEdgeWanError, match="LiveKit media address"): call(args)
    failed = module.load_state(state_path)
    assert failed["last_error_code"] == "public_edge_wan_changed"
    assert failed["caddy"] == state["caddy"] and failed["router"] == state["router"]
    assert module.state_is_healthy(failed) is False
    assert commands == []


@pytest.mark.parametrize("scope", ["private_interface", "assigned_public_interface", "hosted_endpoint", "separate_local_endpoint", "web_only", "router_not_assigned"])
def test_public_media_address_guard_preserves_other_supported_topologies(monkeypatch, scope):
    module = load_module()
    monkeypatch.delenv("LIVEKIT_API_HOST", raising=False)
    assigned = {"192.0.2.10"}
    node_ip, local_ip, port = "8.8.8.8", "192.0.2.10", 7888
    if scope == "private_interface": node_ip = "192.0.2.10"
    elif scope == "assigned_public_interface": assigned.add(node_ip)
    elif scope == "hosted_endpoint": monkeypatch.setenv("LIVEKIT_API_HOST", "https://media.example.test")
    elif scope == "separate_local_endpoint": monkeypatch.setenv("LIVEKIT_API_HOST", "http://127.0.0.1:9999")
    elif scope == "web_only": port = 0
    elif scope == "router_not_assigned": assigned = {"192.0.2.99"}
    monkeypatch.setattr(module, "assigned_local_ipv4s", lambda: assigned)
    module.validate_local_public_media_address(node_ip, "9.9.9.9", local_ip, livekit_port=port)


def dns_edge_state():
    return {
        "provider": "public_https_edge", "public_ip": "198.51.100.20",
        "caddy": {"pid": 701}, "router": {"local_ip": "192.168.50.10", "mappings": []},
        "client": {"target": "http://127.0.0.1:3190", "public_url": "https://app.example.test"},
        "playground": {"target": "http://localhost:3300", "public_url": "https://voice.example.test"},
    }


def test_status_reports_wrong_voice_dns_without_stopping_healthy_edge(monkeypatch, tmp_path, capsys):
    module = load_module()
    state = dns_edge_state()
    path = tmp_path / "edge.json"
    module.save_state(path, state)
    monkeypatch.setattr(module, "state_is_healthy", lambda _state, **_kw: True)
    monkeypatch.setattr(module, "assigned_local_ipv4s", lambda: {"192.168.50.10"})
    monkeypatch.setattr(module, "resolve_public_ipv4_hosts", lambda hosts: {
        host: {"addresses": ["198.51.100.20" if host == "app.example.test" else "203.0.113.44"]}
        for host in hosts
    }, raising=False)
    monkeypatch.setattr(module, "stop_state", lambda _state: pytest.fail("DNS must not stop owned edge"))

    assert module.cmd_status(types.SimpleNamespace(state_file=str(path))) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["runtime_healthy"] is True
    assert result["healthy"] is True
    assert result["public_dns"]["code"] == "public_edge_dns_mismatch"
    assert "voice.example.test" in result["public_dns"]["message"]
    assert result["public_dns"]["hosts"][1]["addresses"] == ["203.0.113.44"]
    saved = module.load_state(path)
    assert saved["caddy"] == state["caddy"]
    assert saved["router"] == state["router"]
    assert "last_error" not in saved


@pytest.mark.parametrize("addresses,expected", [
    (["198.51.100.20"], "match"),
    (["192.168.50.10"], "local_override"),
    (["203.0.113.44"], "mismatch"),
    ([], "unavailable"),
    (["198.51.100.20", "203.0.113.44"], "mismatch"),
])
def test_public_dns_classifies_each_managed_host(monkeypatch, addresses, expected):
    module = load_module()
    monkeypatch.setattr(module, "assigned_local_ipv4s", lambda: {"192.168.50.10"})
    monkeypatch.setattr(module, "resolve_public_ipv4_hosts", lambda hosts: {host: {"addresses": addresses} for host in hosts})
    observed = module.observe_public_edge_dns(dns_edge_state(), force=True)
    assert {host["status"] for host in observed["public_dns"]["hosts"]} == {expected}
    assert observed["public_dns"]["off_network_reachability"] == "not_probed"
    assert "last_error" not in observed


def test_dns_recovery_rechecks_negative_result_and_caches_matching_snapshot(monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "assigned_local_ipv4s", lambda: {"192.168.50.10"})
    clock = [1000.0]
    calls = []
    addresses = ["203.0.113.44"]
    monkeypatch.setattr(module.time, "time", lambda: clock[0])
    def resolve(hosts):
        calls.append(list(hosts))
        return {host: {"addresses": list(addresses)} for host in hosts}
    monkeypatch.setattr(module, "resolve_public_ipv4_hosts", resolve)
    first = module.observe_public_edge_dns(dns_edge_state())
    addresses[:] = ["198.51.100.20"]
    recovered = module.observe_public_edge_dns(first)
    assert recovered["public_dns"]["status"] == "match"
    assert len(calls) == 2
    assert module.observe_public_edge_dns(recovered) == recovered
    assert len(calls) == 2
    clock[0] += module.PUBLIC_EDGE_DNS_CACHE_SECONDS + 1
    module.observe_public_edge_dns(recovered)
    assert len(calls) == 3
    changed = {**recovered, "public_ip": "198.51.100.21"}
    module.observe_public_edge_dns(changed)
    assert len(calls) == 4


def test_dns_observation_does_not_own_external_targets_or_other_remote_modes(monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "resolve_public_ipv4_hosts", lambda _hosts: pytest.fail("Not a managed local public edge"))
    state = dns_edge_state()
    state["provider"] = "tailscale_tailnet_https"
    assert module.observe_public_edge_dns(state) == state
    state["provider"] = "public_https_edge"
    for key in ("client", "playground"):
        state[key]["target"] = "https://managed-provider.example.test"
    assert module.observe_public_edge_dns(state) == state


def test_dns_subprocess_timeout_is_bounded_and_not_an_empty_success(monkeypatch):
    module = load_module(native_dns=True)
    def timed_out(command, **kwargs):
        assert kwargs["timeout"] == module.PUBLIC_EDGE_DNS_TIMEOUT_SECONDS
        assert kwargs.get("shell", False) is False
        raise module.subprocess.TimeoutExpired(command, kwargs["timeout"])
    monkeypatch.setattr(module.subprocess, "run", timed_out)
    result = module.resolve_public_ipv4_hosts(["voice.example.test"])
    assert result["voice.example.test"]["addresses"] == []
    assert result["voice.example.test"]["error"] == "lookup_unavailable"


def test_start_reuses_healthy_edge_even_with_stale_dns(monkeypatch, tmp_path, capsys):
    module = load_module()
    state = dns_edge_state()
    path = tmp_path / "edge.json"
    module.save_state(path, state)
    monkeypatch.setattr(module, "state_is_healthy", lambda value: bool(value))
    monkeypatch.setattr(module, "state_matches_requested_livekit_node_ip", lambda *_args: True)
    monkeypatch.setattr(module, "state_matches_requested_public_edge_surfaces", lambda *_args: True)
    monkeypatch.setattr(module, "assigned_local_ipv4s", lambda: {"192.168.50.10"})
    monkeypatch.setattr(module, "resolve_public_ipv4_hosts", lambda hosts: {host: {"addresses": ["203.0.113.44"]} for host in hosts})
    monkeypatch.setattr(module, "stop_state", lambda _state: pytest.fail("DNS must not retire a healthy edge"))
    args = types.SimpleNamespace(state_file=str(path), log_dir=str(tmp_path / "logs"), provider="public_https_edge")
    assert module.cmd_start(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["public_dns"]["code"] == "public_edge_dns_mismatch"
    assert result["caddy"] == state["caddy"]


def test_dns_stale_lan_override_is_not_accepted_and_malformed_cache_is_rechecked(monkeypatch):
    module = load_module()
    state = dns_edge_state()
    state["public_dns"] = {"checked_at_unix": "invalid", "status": "match"}
    monkeypatch.setattr(module, "assigned_local_ipv4s", lambda: {"192.168.50.11"})
    monkeypatch.setattr(module, "resolve_public_ipv4_hosts", lambda hosts: {
        host: {"addresses": ["192.168.50.10"]} for host in hosts
    })
    assert module.observe_public_edge_dns(state)["public_dns"]["status"] == "mismatch"


def test_native_dns_resolver_validates_bounded_json_result_and_all_hosts(monkeypatch):
    module = load_module(native_dns=True)
    hostnames = ["app.example.test", "voice.example.test"]
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        assert json.loads(command[-1]) == hostnames
        assert kwargs["timeout"] == module.PUBLIC_EDGE_DNS_TIMEOUT_SECONDS
        return types.SimpleNamespace(returncode=0, stdout=json.dumps({host: {"addresses": ["198.51.100.20"]} for host in hostnames}))
    monkeypatch.setattr(module.subprocess, "run", run)
    assert set(module.resolve_public_ipv4_hosts(hostnames)) == set(hostnames)
    assert len(calls) == 1
    monkeypatch.setattr(module.subprocess, "run", lambda *_args, **_kwargs: types.SimpleNamespace(returncode=0, stdout="not json"))
    assert module.resolve_public_ipv4_hosts(hostnames)[hostnames[0]]["error"] == "lookup_unavailable"


def test_mapping_refresh_records_dns_issue_without_replacing_owned_edge(monkeypatch, tmp_path, capsys):
    module = load_module()
    state, _live, commands, _ports, _old_ip, _new_ip = edge_refresh_fixture(module, monkeypatch, moved=False)
    state["client"] = {"target": "http://127.0.0.1:3190", "public_url": "https://app.example.test"}
    path = tmp_path / "edge.json"
    module.save_state(path, state)
    monkeypatch.setattr(module, "resolve_public_ipv4_hosts", lambda hosts: {
        host: {"addresses": ["203.0.113.44"]} for host in hosts
    })
    assert module.cmd_refresh_mappings(types.SimpleNamespace(state_file=str(path), upnp_lease_seconds=14400)) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["public_dns"]["code"] == "public_edge_dns_mismatch"
    assert result["caddy"] == state["caddy"]
    assert result["router"]["mappings"] == state["router"]["mappings"]
    assert len(commands) == len(state["router"]["mappings"])
    assert all("-d" not in command for command in commands)
    assert "last_error" not in result



def test_status_does_not_wait_for_existing_lifecycle_lock(tmp_path):
    module = load_module()
    path = tmp_path / "edge.json"
    module.save_state(path, dns_edge_state())
    lock = module.with_lock(path.with_suffix(".lock"))
    program = """import importlib.util, json, sys, types
from pathlib import Path
spec = importlib.util.spec_from_file_location('status_probe', sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.assigned_local_ipv4s = lambda: {'192.168.50.10'}
m.state_is_healthy = lambda _state, **_kw: True
m.resolve_public_ipv4_hosts = lambda hosts: {h: {'addresses': ['203.0.113.44']} for h in hosts}
raise SystemExit(m.cmd_status(types.SimpleNamespace(state_file=sys.argv[2])))
"""
    try:
        result = module.subprocess.run(
            [module.sys.executable, "-I", "-c", program, str(MODULE_PATH), str(path)],
            capture_output=True, text=True, timeout=2,
        )
    finally:
        module.fcntl.flock(lock.fileno(), module.fcntl.LOCK_UN)
        lock.close()
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["healthy"] is True
    assert output["public_dns"]["code"] == "public_edge_dns_mismatch"
    assert "public_dns" not in module.load_state(path)


@pytest.mark.parametrize("runtime_healthy", [True, False])
@pytest.mark.parametrize("dns_status", ["match", "mismatch", "unavailable"])
def test_status_exit_code_remains_runtime_health_for_launcher_consumers(monkeypatch, tmp_path, capsys, runtime_healthy, dns_status):
    module = load_module()
    path = tmp_path / "edge.json"
    module.save_state(path, dns_edge_state())
    monkeypatch.setattr(module, "assigned_local_ipv4s", lambda: {"192.168.50.10"})
    monkeypatch.setattr(module, "observe_public_edge_dns", lambda state, **_kw: {**state, "public_dns": {"status": dns_status}})
    monkeypatch.setattr(module, "state_is_healthy", lambda _state, **_kw: runtime_healthy)
    assert module.cmd_status(types.SimpleNamespace(state_file=str(path))) == (0 if runtime_healthy else 1)
    result = json.loads(capsys.readouterr().out)
    assert result["healthy"] is runtime_healthy
    assert result["runtime_healthy"] is runtime_healthy
    assert result["public_dns"]["status"] == dns_status


def test_status_keeps_runtime_result_when_diagnostic_save_is_unwritable(monkeypatch, tmp_path, capsys):
    module = load_module()
    path = tmp_path / "edge.json"
    module.save_state(path, dns_edge_state())
    monkeypatch.setattr(module, "assigned_local_ipv4s", lambda: {"192.168.50.10"})
    monkeypatch.setattr(module, "state_is_healthy", lambda _state, **_kw: True)
    monkeypatch.setattr(module, "resolve_public_ipv4_hosts", lambda hosts: {
        host: {"addresses": ["203.0.113.44"]} for host in hosts
    })
    monkeypatch.setattr(module, "save_state", lambda *_args: (_ for _ in ()).throw(PermissionError("Read-only state")))
    assert module.cmd_status(types.SimpleNamespace(state_file=str(path))) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["healthy"] is True
    assert result["public_dns"]["code"] == "public_edge_dns_mismatch"
    assert "public_dns" not in module.load_state(path)


def test_status_never_overwrites_a_newer_lifecycle_snapshot(monkeypatch, tmp_path, capsys):
    module = load_module()
    initial = dns_edge_state()
    newer = {**initial, "created_at": "2030-01-02T03:04:05Z"}
    reads = iter([initial, newer])
    saved = []
    monkeypatch.setattr(module, "load_state", lambda _path: next(reads))
    monkeypatch.setattr(module, "assigned_local_ipv4s", lambda: {"192.168.50.10"})
    monkeypatch.setattr(module, "state_is_healthy", lambda _state, **_kw: True)
    monkeypatch.setattr(module, "save_state", lambda *_args: saved.append(_args))
    assert module.cmd_status(types.SimpleNamespace(state_file=str(tmp_path / "edge.json"))) == 0
    assert saved == []
    assert json.loads(capsys.readouterr().out)["healthy"] is True


def test_status_reuses_one_fresh_interface_observation(monkeypatch, tmp_path, capsys):
    module = load_module()
    path = tmp_path / "edge.json"
    module.save_state(path, dns_edge_state())
    scans = []
    def assigned():
        scans.append(True)
        return {"192.168.50.10"}
    monkeypatch.setattr(module, "assigned_local_ipv4s", assigned)
    monkeypatch.setattr(module, "probe_local_endpoint", lambda *_args, **_kw: True)
    monkeypatch.setattr(module, "pid_is_running", lambda *_args: True)
    assert module.cmd_status(types.SimpleNamespace(state_file=str(path))) == 0
    assert json.loads(capsys.readouterr().out)["healthy"] is True
    assert scans == [True]
