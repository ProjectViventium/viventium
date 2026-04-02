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
        "playground": {
            "pid": 123,
            "target": "http://127.0.0.1:3300",
            "public_url": "https://voice.example.trycloudflare.com",
        },
        "livekit": {
            "pid": 456,
            "target": "http://127.0.0.1:7888",
            "public_url": "https://livekit.example.trycloudflare.com",
        },
        "public_playground_url": "https://voice.example.trycloudflare.com",
        "public_livekit_url": "wss://livekit.example.trycloudflare.com",
    }

    assert module.state_is_healthy(state) is True
    assert probed_urls == [
        "http://127.0.0.1:3300",
        "http://127.0.0.1:7888",
    ]


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
        if url == "http://127.0.0.1:3300":
            return False
        return True

    monkeypatch.setattr(module, "probe_local_endpoint", fake_probe)

    state = {
        "playground": {
            "pid": 123,
            "target": "http://127.0.0.1:3300",
            "public_url": "https://voice.example.trycloudflare.com",
        },
        "livekit": {
            "pid": 456,
            "target": "http://127.0.0.1:7888",
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

    assert module.probe_local_endpoint("http://127.0.0.1:3300") is True
    assert captured == [(("127.0.0.1", 3300), module.DEFAULT_HEALTH_TIMEOUT_SECONDS)]


def test_wait_for_state_ready_retries_until_state_turns_healthy(monkeypatch) -> None:
    module = load_module()
    checks = {"count": 0}

    def fake_state_is_healthy(_state):
        checks["count"] += 1
        return checks["count"] >= 3

    monkeypatch.setattr(module, "state_is_healthy", fake_state_is_healthy)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    assert module.wait_for_state_ready({"public_playground_url": "https://x"}, 5) is True
    assert checks["count"] == 3


def test_cmd_start_fails_when_public_tunnels_never_become_ready(monkeypatch, tmp_path: Path) -> None:
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
    monkeypatch.setattr(
        module,
        "start_quick_tunnel",
        lambda *_args, **kwargs: (111 if "3300" in kwargs["target_url"] else 222, "https://example.trycloudflare.com"),
    )
    monkeypatch.setattr(module, "wait_for_state_ready", lambda _state, _timeout: False)
    stopped: list[int] = []
    monkeypatch.setattr(module, "stop_pid", lambda pid: stopped.append(pid))
    monkeypatch.setattr(module, "save_state", lambda *_args, **_kwargs: None)

    args = types.SimpleNamespace(
        state_file=str(tmp_path / "public-network.json"),
        log_dir=str(tmp_path / "logs"),
        playground_port=3300,
        livekit_port=7888,
        provider="cloudflare_quick_tunnel",
        auto_install=False,
        timeout_seconds=5,
        command="start",
    )

    with pytest.raises(RuntimeError, match="publicly reachable"):
        module.cmd_start(args)

    assert stopped == [111, 222]


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
            "--playground-port",
            "3300",
            "--livekit-port",
            "7888",
        ],
    )

    args = module.parse_args()

    assert args.timeout_seconds == 165
