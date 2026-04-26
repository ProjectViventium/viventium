from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT_PATH = REPO_ROOT / "scripts/viventium/preflight.py"
YAML_SITE_PACKAGES = str(Path(yaml.__file__).resolve().parents[1])


def preflight_subprocess_env(tmp_path: Path, *, path: str = "/usr/bin:/bin") -> dict[str, str]:
    return {
        "PATH": path,
        "HOME": str(tmp_path),
        "TERM": "xterm-256color",
        "PYTHONPATH": os.pathsep.join(
            entry for entry in [YAML_SITE_PACKAGES, os.environ.get("PYTHONPATH", "")] if entry
        ),
        "VIVENTIUM_PREFLIGHT_DISABLE_HOST_PATH_DISCOVERY": "1",
        "VIVENTIUM_DOCKER_APP_DIRS": str(tmp_path / "Applications"),
    }


def load_preflight_module():
    spec = importlib.util.spec_from_file_location("viventium_preflight_test", PREFLIGHT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_public_edge_cgnat_details_flags_router_public_ip_mismatch(monkeypatch) -> None:
    module = load_preflight_module()
    monkeypatch.setattr(module, "upnpc_router_external_ipv4", lambda: "100.64.0.5")
    monkeypatch.setattr(module, "discover_public_ipv4", lambda: "203.0.113.42")

    assert module.public_edge_cgnat_details() == (True, "100.64.0.5", "203.0.113.42")


def test_public_edge_cgnat_details_ignores_matching_public_ip(monkeypatch) -> None:
    module = load_preflight_module()
    monkeypatch.setattr(module, "upnpc_router_external_ipv4", lambda: "203.0.113.42")
    monkeypatch.setattr(module, "discover_public_ipv4", lambda: "203.0.113.42")

    assert module.public_edge_cgnat_details() == (False, "203.0.113.42", "203.0.113.42")


def test_ffmpeg_runtime_ready_rejects_present_broken_binary(monkeypatch) -> None:
    module = load_preflight_module()
    monkeypatch.setattr(module, "command_exists", lambda command: command == "ffmpeg")
    monkeypatch.setattr(
        module,
        "run_checked",
        lambda args, timeout_seconds=None: subprocess.CompletedProcess(
            args=args,
            returncode=-6,
            stdout="",
            stderr="Library not loaded",
        ),
    )

    assert module.ffmpeg_runtime_ready() is False


def test_ffmpeg_runtime_ready_accepts_successful_probe(monkeypatch) -> None:
    module = load_preflight_module()
    monkeypatch.setattr(module, "command_exists", lambda command: command == "ffmpeg")
    monkeypatch.setattr(
        module,
        "run_checked",
        lambda args, timeout_seconds=None: subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="",
            stderr="",
        ),
    )

    assert module.ffmpeg_runtime_ready() is True


def test_command_runtime_ready_rejects_present_broken_binary(monkeypatch) -> None:
    module = load_preflight_module()
    calls: list[tuple[list[str], float | None]] = []

    def fake_run_checked(args: list[str], *, timeout_seconds: float | None = None):
        calls.append((args, timeout_seconds))
        return subprocess.CompletedProcess(
            args=args,
            returncode=-6,
            stdout="",
            stderr="Library not loaded",
        )

    monkeypatch.setattr(module, "refresh_brew_paths", lambda: None)
    monkeypatch.setattr(module, "command_exists", lambda command: command == "pnpm")
    monkeypatch.setattr(module, "run_checked", fake_run_checked)

    assert module.command_runtime_ready("pnpm", ["--version"]) is False
    assert calls == [(["pnpm", "--version"], module.DEFAULT_CLI_RUNTIME_PROBE_TIMEOUT_SECONDS)]


def test_command_runtime_ready_times_out_cleanly(monkeypatch) -> None:
    module = load_preflight_module()

    monkeypatch.setattr(module, "refresh_brew_paths", lambda: None)
    monkeypatch.setattr(module, "command_exists", lambda command: command == "meilisearch")
    monkeypatch.setattr(
        module,
        "run_checked",
        lambda args, timeout_seconds=None: subprocess.CompletedProcess(
            args=args,
            returncode=124,
            stdout="",
            stderr="Timed out",
        ),
    )

    assert module.command_runtime_ready("meilisearch", ["--version"]) is False


@pytest.mark.parametrize(
    ("helper_name", "item_key", "formula", "config"),
    [
        ("pnpm_runtime_ready", "pnpm", "pnpm", {}),
        ("uv_runtime_ready", "uv", "uv", {}),
        (
            "ollama_cli_runtime_ready",
            "ollama",
            "ollama",
            {
                "runtime": {"personalization": {"default_conversation_recall": True}},
            },
        ),
        (
            "mongod_runtime_ready",
            "mongod",
            "mongodb/brew/mongodb-community@8.0",
            {"install": {"mode": "native"}},
        ),
        (
            "meilisearch_runtime_ready",
            "meilisearch",
            "meilisearch",
            {"install": {"mode": "native"}},
        ),
        (
            "livekit_runtime_ready",
            "livekit",
            "livekit",
            {"install": {"mode": "native"}, "voice": {"mode": "local"}},
        ),
        (
            "cloudflared_runtime_ready",
            "cloudflared",
            "cloudflared",
            {
                "voice": {"mode": "local"},
                "runtime": {"network": {"remote_call_mode": "cloudflare_quick_tunnel"}},
            },
        ),
        (
            "tailscale_cli_runtime_ready",
            "tailscale",
            "tailscale",
            {"runtime": {"network": {"remote_call_mode": "tailscale_tailnet_https"}}},
        ),
        (
            "caddy_runtime_ready",
            "public_edge_caddy",
            "caddy",
            {"runtime": {"network": {"remote_call_mode": "public_https_edge"}}},
        ),
        (
            "upnpc_runtime_ready",
            "public_edge_upnpc",
            "miniupnpc",
            {"runtime": {"network": {"remote_call_mode": "public_https_edge"}}},
        ),
    ],
)
def test_preflight_uses_runtime_probes_for_brew_prereqs(
    monkeypatch,
    helper_name: str,
    item_key: str,
    formula: str,
    config: dict,
) -> None:
    module = load_preflight_module()

    for ready_helper in (
        "pnpm_runtime_ready",
        "uv_runtime_ready",
        "ollama_cli_runtime_ready",
        "mongod_runtime_ready",
        "meilisearch_runtime_ready",
        "livekit_runtime_ready",
        "cloudflared_runtime_ready",
        "tailscale_cli_runtime_ready",
        "caddy_runtime_ready",
        "upnpc_runtime_ready",
    ):
        monkeypatch.setattr(module, ready_helper, lambda: True)
    monkeypatch.setattr(module, helper_name, lambda: False)
    monkeypatch.setattr(module, "node_runtime_supported", lambda: True)
    monkeypatch.setattr(module, "command_exists", lambda command: command in {"git", "security", "netbird"})
    monkeypatch.setattr(module, "xcode_cli_tools_installed", lambda: True)
    monkeypatch.setattr(module, "docker_desktop_installed", lambda: True)
    monkeypatch.setattr(module, "docker_daemon_ready", lambda: True)
    monkeypatch.setattr(module, "tailscale_service_ready", lambda: True)
    monkeypatch.setattr(module, "netbird_missing_remote_origin_fields", lambda config: [])
    monkeypatch.setattr(module, "netbird_livekit_node_ip_ready", lambda config: True)
    monkeypatch.setattr(module, "upnpc_router_ready", lambda: True)
    monkeypatch.setattr(module, "public_edge_cgnat_details", lambda: (False, "", ""))

    items = module.build_preflight_items(config)
    target = next(item for item in items if item.key == item_key)

    assert target.status == "missing"
    assert target.install_kind == "brew_formula"
    assert target.formula == formula


def test_preflight_aggregates_missing_native_prereqs(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
version: 1
install:
  mode: native
runtime:
  profile: isolated
  network:
    remote_call_mode: cloudflare_quick_tunnel
voice:
  mode: local
integrations:
  telegram:
    enabled: true
""".strip()
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(PREFLIGHT_PATH), "--config", str(config_path)],
        cwd=REPO_ROOT,
        env=preflight_subprocess_env(tmp_path),
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "Viventium Preflight" in completed.stdout
    assert "node@20" in completed.stdout
    assert "pnpm" in completed.stdout
    assert "uv" in completed.stdout
    assert "ffmpeg" in completed.stdout
    assert "python@3.12" in completed.stdout
    assert "mongodb-community@8.0" in completed.stdout
    assert "meilisearch" in completed.stdout
    assert "livekit" in completed.stdout
    assert "cloudflared" in completed.stdout
    assert "Homebrew" in completed.stdout
    assert "Docker Desktop" not in completed.stdout
    assert "Mac Prerequisites" in completed.stdout


def test_preflight_flags_local_telegram_bot_api_prereqs_when_enabled(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
version: 1
install:
  mode: native
runtime:
  profile: isolated
voice:
  mode: disabled
integrations:
  telegram:
    enabled: true
    local_bot_api:
      enabled: true
""".strip()
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(PREFLIGHT_PATH), "--config", str(config_path)],
        cwd=REPO_ROOT,
        env=preflight_subprocess_env(tmp_path),
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "telegram-bot-api" in completed.stdout
    assert "Telegram local Bot API credentials" in completed.stdout


def test_preflight_legacy_auto_remote_call_mode_defaults_to_disabled(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
version: 1
install:
  mode: native
runtime:
  profile: isolated
  network:
    remote_call_mode: auto
voice:
  mode: local
""".strip()
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(PREFLIGHT_PATH), "--config", str(config_path)],
        cwd=REPO_ROOT,
        env=preflight_subprocess_env(tmp_path),
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "Remote calls: disabled" in completed.stdout
    assert "cloudflared" not in completed.stdout


def test_preflight_tailscale_mode_requires_tailscale_even_without_voice(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
version: 1
install:
  mode: native
runtime:
  profile: isolated
  network:
    remote_call_mode: tailscale_tailnet_https
voice:
  mode: disabled
""".strip()
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(PREFLIGHT_PATH), "--config", str(config_path)],
        cwd=REPO_ROOT,
        env=preflight_subprocess_env(tmp_path),
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "Remote calls: tailscale_tailnet_https" in completed.stdout
    assert "tailscale" in completed.stdout
    assert "cloudflared" not in completed.stdout


def test_preflight_netbird_mode_requires_netbird_and_caddy(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
version: 1
install:
  mode: native
runtime:
  profile: isolated
  network:
    remote_call_mode: netbird_selfhosted_mesh
voice:
  mode: disabled
""".strip()
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(PREFLIGHT_PATH), "--config", str(config_path)],
        cwd=REPO_ROOT,
        env=preflight_subprocess_env(tmp_path),
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "Remote calls: netbird_selfhosted_mesh" in completed.stdout
    assert "NetBird client" in completed.stdout
    assert "caddy" in completed.stdout
    assert "NetBird remote origins" in completed.stdout
    assert "public_client_origin" in completed.stdout


@pytest.mark.parametrize("remote_call_mode", ["public_https_edge", "custom_domain"])
def test_preflight_public_https_edge_requires_caddy_and_router_mapping_tools(
    tmp_path: Path, remote_call_mode: str
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
version: 1
install:
  mode: native
runtime:
  profile: isolated
  network:
    remote_call_mode: {remote_call_mode}
voice:
  mode: local
""".strip()
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(PREFLIGHT_PATH), "--config", str(config_path)],
        cwd=REPO_ROOT,
        env=preflight_subprocess_env(tmp_path),
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "Remote calls: public_https_edge" in completed.stdout
    assert "caddy" in completed.stdout
    assert "miniupnpc" in completed.stdout


def test_preflight_native_without_voice_does_not_require_python312(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
version: 1
install:
  mode: native
runtime:
  profile: isolated
voice:
  mode: disabled
""".strip()
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(PREFLIGHT_PATH), "--config", str(config_path)],
        cwd=REPO_ROOT,
        env=preflight_subprocess_env(tmp_path),
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "ffmpeg" not in completed.stdout
    assert "python@3.12" not in completed.stdout


def test_preflight_voice_local_without_telegram_does_not_require_ffmpeg(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
version: 1
install:
  mode: native
runtime:
  profile: isolated
voice:
  mode: local
  stt_provider: whisper_local
integrations:
  telegram:
    enabled: false
""".strip()
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(PREFLIGHT_PATH), "--config", str(config_path)],
        cwd=REPO_ROOT,
        env=preflight_subprocess_env(tmp_path),
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "python@3.12" in completed.stdout
    assert "livekit" in completed.stdout
    assert "ffmpeg" not in completed.stdout


def test_preflight_native_ms365_requires_docker_desktop(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
version: 1
install:
  mode: native
runtime:
  profile: isolated
voice:
  mode: disabled
integrations:
  ms365:
    enabled: true
""".strip()
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(PREFLIGHT_PATH), "--config", str(config_path)],
        cwd=REPO_ROOT,
        env=preflight_subprocess_env(tmp_path),
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "MS365" in completed.stdout
    assert "Docker Desktop" in completed.stdout
    assert "Conversation Recall" not in completed.stdout


def test_preflight_native_conversation_recall_requires_docker_and_ollama(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
version: 1
install:
  mode: native
runtime:
  profile: isolated
  personalization:
    default_conversation_recall: true
""".strip()
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(PREFLIGHT_PATH), "--config", str(config_path)],
        cwd=REPO_ROOT,
        env=preflight_subprocess_env(tmp_path),
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "Docker Desktop" in completed.stdout
    assert "Conversation Recall" in completed.stdout
    assert "ollama" in completed.stdout
    assert "Code Interpreter" not in completed.stdout
    assert "Web Search" not in completed.stdout


def test_preflight_native_recommended_defaults_do_not_require_docker(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
version: 1
install:
  mode: native
runtime:
  profile: isolated
voice:
  mode: disabled
integrations:
  ms365:
    enabled: false
""".strip()
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(PREFLIGHT_PATH), "--config", str(config_path)],
        cwd=REPO_ROOT,
        env=preflight_subprocess_env(tmp_path),
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "Conversation Recall" not in completed.stdout
    assert "Code Interpreter" not in completed.stdout
    assert "Web Search" not in completed.stdout
    assert "Docker Desktop" not in completed.stdout


def test_preflight_requires_validated_node20_when_newer_node_is_present(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
version: 1
install:
  mode: native
runtime:
  profile: isolated
voice:
  mode: disabled
""".strip()
        + "\n",
        encoding="utf-8",
    )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name, body in {
        "node": "#!/bin/sh\nprintf 'v25.8.1\\n'\n",
        "npm": "#!/bin/sh\nprintf '11.11.0\\n'\n",
        "git": "#!/bin/sh\nexit 0\n",
        "security": "#!/bin/sh\nexit 0\n",
        "xcode-select": "#!/bin/sh\nprintf '%s\\n' '/Library/Developer/CommandLineTools'\n",
    }.items():
        path = bin_dir / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)

    completed = subprocess.run(
        [sys.executable, str(PREFLIGHT_PATH), "--config", str(config_path)],
        cwd=REPO_ROOT,
        env=preflight_subprocess_env(tmp_path, path=str(bin_dir)),
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "node@20" in completed.stdout
    assert "validated Node runtime" in completed.stdout


def test_preflight_treats_existing_docker_app_as_installed_for_ms365(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
version: 1
install:
  mode: native
runtime:
  profile: isolated
voice:
  mode: disabled
integrations:
  ms365:
    enabled: true
""".strip()
        + "\n",
        encoding="utf-8",
    )

    docker_bin = (
        tmp_path
        / "Applications"
        / "Docker.app"
        / "Contents"
        / "Resources"
        / "bin"
        / "docker"
    )
    docker_bin.parent.mkdir(parents=True, exist_ok=True)
    docker_bin.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    docker_bin.chmod(0o755)

    completed = subprocess.run(
        [sys.executable, str(PREFLIGHT_PATH), "--config", str(config_path)],
        cwd=REPO_ROOT,
        env=preflight_subprocess_env(tmp_path),
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "Docker daemon running" in completed.stdout
    assert "open -a Docker" in completed.stdout
    assert "brew install --cask docker" not in completed.stdout


def test_install_brew_casks_tolerates_existing_docker_app(monkeypatch, tmp_path: Path) -> None:
    preflight = load_preflight_module()

    docker_bin = (
        tmp_path
        / "Applications"
        / "Docker.app"
        / "Contents"
        / "Resources"
        / "bin"
        / "docker"
    )
    docker_bin.parent.mkdir(parents=True, exist_ok=True)
    docker_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    docker_bin.chmod(0o755)

    calls: list[list[str]] = []

    def fake_run_checked(args: list[str]):
        calls.append(args)
        if args[:4] == ["brew", "install", "--cask", "docker"]:
            return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="app exists")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setenv("VIVENTIUM_DOCKER_APP_DIRS", str(tmp_path / "Applications"))
    monkeypatch.setattr(preflight, "run_checked", fake_run_checked)
    monkeypatch.setattr(preflight, "style", lambda text, _code: text)

    preflight.install_brew_casks(["docker"])

    assert calls == [["brew", "install", "--cask", "docker"]]


def test_install_brew_formulas_accepts_runtime_when_homebrew_returns_nonzero(monkeypatch) -> None:
    preflight = load_preflight_module()

    calls: list[list[str]] = []

    def fake_run_checked(args: list[str]):
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="link warning")

    monkeypatch.setattr(preflight, "run_checked", fake_run_checked)
    monkeypatch.setattr(preflight, "refresh_brew_paths", lambda: None)
    monkeypatch.setattr(preflight, "formula_usable", lambda formula: formula == "node@20")

    preflight.install_brew_formulas(["node@20"])

    assert calls == [["brew", "install", "node@20"]]


def test_install_brew_formulas_retries_when_installed_binary_cannot_execute(monkeypatch) -> None:
    preflight = load_preflight_module()

    calls: list[list[str]] = []
    usable_results = iter([False, True])

    def fake_run_checked(args: list[str]):
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(preflight, "run_checked", fake_run_checked)
    monkeypatch.setattr(preflight, "refresh_brew_paths", lambda: None)
    monkeypatch.setattr(preflight, "formula_usable", lambda _formula: next(usable_results))

    preflight.install_brew_formulas(["ffmpeg"])

    assert calls == [["brew", "install", "ffmpeg"], ["brew", "reinstall", "ffmpeg"]]


def test_install_brew_formulas_reports_homebrew_drift_when_reinstall_cannot_fix_runtime(
    monkeypatch,
) -> None:
    preflight = load_preflight_module()

    calls: list[list[str]] = []

    def fake_run_checked(args: list[str]):
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(preflight, "run_checked", fake_run_checked)
    monkeypatch.setattr(preflight, "refresh_brew_paths", lambda: None)
    monkeypatch.setattr(preflight, "formula_usable", lambda _formula: False)

    with pytest.raises(SystemExit) as excinfo:
        preflight.install_brew_formulas(["ffmpeg"])

    assert calls == [["brew", "install", "ffmpeg"], ["brew", "reinstall", "ffmpeg"]]
    message = str(excinfo.value)
    assert "Homebrew dependency drift" in message
    assert "brew upgrade" in message
    assert "brew doctor" in message


@pytest.mark.parametrize(
    ("formula", "helper_name"),
    [
        ("pnpm", "pnpm_runtime_ready"),
        ("uv", "uv_runtime_ready"),
        ("ollama", "ollama_cli_runtime_ready"),
        ("ffmpeg", "ffmpeg_runtime_ready"),
        ("mongodb/brew/mongodb-community@8.0", "mongod_runtime_ready"),
        ("meilisearch", "meilisearch_runtime_ready"),
        ("livekit", "livekit_runtime_ready"),
        ("cloudflared", "cloudflared_runtime_ready"),
        ("tailscale", "tailscale_cli_runtime_ready"),
        ("caddy", "caddy_runtime_ready"),
        ("miniupnpc", "upnpc_runtime_ready"),
    ],
)
def test_formula_usable_delegates_to_runtime_probe(monkeypatch, formula: str, helper_name: str) -> None:
    preflight = load_preflight_module()
    calls: list[str] = []

    def fake_probe() -> bool:
        calls.append(helper_name)
        return True

    monkeypatch.setattr(preflight, "refresh_brew_paths", lambda: None)
    monkeypatch.setattr(preflight, helper_name, fake_probe)

    assert preflight.formula_usable(formula) is True
    assert calls == [helper_name]


def test_docker_daemon_ready_uses_bounded_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    preflight = load_preflight_module()

    calls: list[tuple[list[str], float | None]] = []

    def fake_run_checked(args: list[str], *, timeout_seconds: float | None = None):
        calls.append((args, timeout_seconds))
        return subprocess.CompletedProcess(args=args, returncode=124, stdout="", stderr="timed out")

    monkeypatch.setenv("VIVENTIUM_DOCKER_READINESS_TIMEOUT_SECONDS", "1.5")
    monkeypatch.setattr(preflight, "docker_cli_path", lambda: "/fake/docker")
    monkeypatch.setattr(preflight, "run_checked", fake_run_checked)

    assert preflight.docker_daemon_ready() is False
    assert calls == [(["/fake/docker", "ps"], 1.5)]


def test_docker_desktop_installed_ignores_stray_docker_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    preflight = load_preflight_module()

    monkeypatch.setattr(preflight, "docker_app_bundle_paths", lambda: [])
    monkeypatch.setattr(preflight, "brew_cask_installed", lambda _cask: False)
    monkeypatch.setattr(preflight, "docker_cli_path", lambda: "/usr/local/bin/docker")

    assert preflight.docker_desktop_installed() is False


def test_wait_for_manual_items_keeps_rechecking_until_docker_is_ready(monkeypatch) -> None:
    preflight = load_preflight_module()

    docker_item = preflight.PreflightItem(
        key="docker_daemon",
        label="Docker daemon running",
        category="local docker services",
        reason="Web Search startup requires Docker Desktop running before local services start",
        status="missing",
        install_kind="manual",
        manual_command="open -a Docker",
    )

    class FakeUI:
        def __init__(self) -> None:
            self.notes: list[str] = []
            self.successes: list[str] = []

        def print_section(self, _title: str, _message: str, style: str = "cyan") -> None:
            return None

        def print_note(self, message: str) -> None:
            self.notes.append(message)

        def print_blank(self) -> None:
            return None

        def print_warning(self, _message: str) -> None:
            return None

        def print_success(self, message: str) -> None:
            self.successes.append(message)

        def confirm(self, _prompt: str, default: bool = False) -> bool:
            return default

    states = iter(
        [
            [docker_item],
            [],
        ]
    )
    ticks = iter(range(100))

    monkeypatch.setattr(preflight, "auto_start_safe_manual_items", lambda items: None)
    monkeypatch.setattr(preflight, "build_preflight_items", lambda config: next(states))
    monkeypatch.setattr(preflight.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(preflight.time, "time", lambda: float(next(ticks)))

    ui = FakeUI()
    preflight.wait_for_manual_items(ui, {"install": {"mode": "native"}}, [docker_item], False)

    assert any("Docker Desktop" in note for note in ui.notes)
    assert ui.successes == ["Manual setup finished. Continuing the Viventium install."]


def test_auto_start_safe_manual_items_uses_bounded_docker_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    preflight = load_preflight_module()

    docker_item = preflight.PreflightItem(
        key="docker_daemon",
        label="Docker daemon running",
        category="local docker services",
        reason="Web Search startup requires Docker Desktop running before local services start",
        status="missing",
        install_kind="manual",
        manual_command="open -a Docker",
    )
    probe_results = iter([False, False, True])
    open_calls: list[list[str]] = []

    monkeypatch.setattr(preflight.subprocess, "run", lambda args, check=False: open_calls.append(args))
    monkeypatch.setattr(preflight, "docker_cli_path", lambda: "/fake/docker")
    monkeypatch.setattr(preflight, "docker_daemon_ready", lambda: next(probe_results))
    monkeypatch.setattr(preflight.time, "sleep", lambda _seconds: None)

    preflight.auto_start_safe_manual_items([docker_item])

    assert open_calls == [["open", "-a", "Docker"]]


def test_wait_for_manual_items_exits_cleanly_in_non_interactive_mode() -> None:
    preflight = load_preflight_module()

    docker_item = preflight.PreflightItem(
        key="docker_daemon",
        label="Docker daemon running",
        category="local docker services",
        reason="Web Search startup requires Docker Desktop running before local services start",
        status="missing",
        install_kind="manual",
        manual_command="open -a Docker",
    )

    class FakeUI:
        def print_section(self, _title: str, _message: str, style: str = "cyan") -> None:
            return None

        def print_note(self, _message: str) -> None:
            return None

        def print_blank(self) -> None:
            return None

        def print_warning(self, _message: str) -> None:
            return None

        def print_success(self, _message: str) -> None:
            return None

        def confirm(self, _prompt: str, default: bool = False) -> bool:
            return default

    with pytest.raises(SystemExit) as excinfo:
        preflight.wait_for_manual_items(
            FakeUI(),
            {"install": {"mode": "native"}},
            [docker_item],
            True,
        )

    assert "Manual prerequisites still need attention" in str(excinfo.value)
    assert "open -a Docker" in str(excinfo.value)


def test_queue_local_web_search_prewarm_starts_background_pull_for_local_services(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    preflight = load_preflight_module()

    config_path = tmp_path / "Library" / "Application Support" / "Viventium" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("version: 1\n", encoding="utf-8")

    config = {
        "integrations": {
            "web_search": {
                "enabled": True,
                "search_provider": "searxng",
                "scraper_provider": "firecrawl",
            }
        }
    }

    popen_calls: list[list[str]] = []

    class FakePopen:
        def __init__(self, args, **_kwargs) -> None:
            popen_calls.append(args)

    monkeypatch.setattr(preflight, "docker_daemon_ready", lambda: True)
    monkeypatch.setattr(preflight, "docker_prewarm_running", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(preflight.subprocess, "Popen", FakePopen)

    preflight.queue_local_web_search_prewarm(config_path, config)

    assert len(popen_calls) == 2
    joined = "\n".join(" ".join(call) for call in popen_calls)
    assert "docker compose -f" in joined
    assert "searxng/docker-compose.yml" in joined
    assert "firecrawl/docker-compose.yml" in joined


def test_queue_local_web_search_prewarm_skips_when_docker_not_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    preflight = load_preflight_module()

    config_path = tmp_path / "config.yaml"
    config_path.write_text("version: 1\n", encoding="utf-8")
    config = {
        "integrations": {
            "web_search": {
                "enabled": True,
                "search_provider": "searxng",
                "scraper_provider": "firecrawl",
            }
        }
    }

    class UnexpectedPopen:
        def __init__(self, *_args, **_kwargs) -> None:
            raise AssertionError("prewarm should not start when docker is unavailable")

    monkeypatch.setattr(preflight, "docker_daemon_ready", lambda: False)
    monkeypatch.setattr(preflight.subprocess, "Popen", UnexpectedPopen)

    preflight.queue_local_web_search_prewarm(config_path, config)


def test_local_firecrawl_memory_warning_flags_small_docker_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preflight = load_preflight_module()

    config = {
        "integrations": {
            "web_search": {
                "enabled": True,
                "search_provider": "searxng",
                "scraper_provider": "firecrawl",
            }
        }
    }

    monkeypatch.setattr(preflight, "docker_total_memory_bytes", lambda: 3 * 1024 * 1024 * 1024)

    warning = preflight.local_firecrawl_memory_warning(config)

    assert warning is not None
    assert "3.0 GB" in warning
    assert "4 GB" in warning
    assert "Firecrawl API" in warning
