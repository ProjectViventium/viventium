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
