from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
BIN_VIVENTIUM = REPO_ROOT / "bin" / "viventium"
CONFIG_COMPILER = REPO_ROOT / "scripts" / "viventium" / "config_compiler.py"
DEV_RUNTIME = REPO_ROOT / "scripts" / "viventium" / "dev_runtime.py"
WORKFLOWS = REPO_ROOT / "scripts" / "viventium" / "workflows.py"
UPGRADE_CHECK = REPO_ROOT / "scripts" / "viventium" / "upgrade_check.py"
HELPER_LIFECYCLE_QA = REPO_ROOT / "scripts" / "viventium" / "qa_helper_lifecycle.py"
PASSWORD_RESET_LINK_SCRIPT = (
    REPO_ROOT / "viventium_v0_4" / "LibreChat" / "config" / "issue-password-reset-link.js"
)
HELPER_SOURCE = (
    REPO_ROOT
    / "apps"
    / "macos"
    / "ViventiumHelper"
    / "Sources"
    / "ViventiumHelper"
    / "ViventiumHelperApp.swift"
)


def minimal_config() -> dict:
    return {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "profile": "isolated",
            "ports": {
                "lc_api_port": 3180,
                "lc_frontend_port": 3190,
                "playground_port": 3300,
                "voice_gateway_health_port": 8301,
                "rag_api_port": 8110,
                "google_mcp_port": 8111,
            },
            "personalization": {"default_conversation_recall": True},
            "memory_hardening": {"enabled": False},
            "auth": {"allow_registration": True, "allow_password_reset": False},
        },
        "llm": {
            "activation": {"provider": "groq", "auth_mode": "api_key", "secret_ref": "keychain://viventium/groq_api_key"},
            "primary": {"provider": "openai", "auth_mode": "connected_account"},
            "secondary": {"provider": "anthropic", "auth_mode": "api_key", "secret_ref": "keychain://viventium/anthropic_api_key"},
        },
        "voice": {"mode": "local", "stt_provider": "whisper_local", "tts_provider": "browser"},
        "integrations": {
            "web_search": {"enabled": True, "search_provider": "searxng", "scraper_provider": "firecrawl"},
            "google_workspace": {"enabled": True},
            "ms365": {"enabled": True},
            "glasshive": {"enabled": False},
        },
    }


def test_dev_env_offsets_only_app_facing_ports_and_records_shared_singletons(tmp_path: Path) -> None:
    app_support = tmp_path / "App Support" / "Viventium"
    config = app_support / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(yaml.safe_dump(minimal_config(), sort_keys=False), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            str(DEV_RUNTIME),
            "--repo-root",
            str(REPO_ROOT),
            "--app-support-dir",
            str(app_support),
            "--config-file",
            str(config),
            "create",
            "dev",
        ],
        check=True,
    )

    dev_config = yaml.safe_load((app_support / "dev-envs" / "dev" / "config.yaml").read_text(encoding="utf-8"))
    ports = dev_config["runtime"]["ports"]
    assert ports["lc_api_port"] == 4180
    assert ports["lc_frontend_port"] == 4190
    assert ports["playground_port"] == 4300
    assert ports["voice_gateway_health_port"] == 9301
    assert ports["rag_api_port"] == 8110
    assert ports["google_mcp_port"] == 8111
    assert dev_config["runtime"]["dev_env"]["shared_singleton_services"] == [
        "recall_rag",
        "searxng",
        "firecrawl",
        "google_workspace_mcp",
        "ms365_mcp",
    ]


def test_dev_env_shared_singletons_compile_without_duplicate_start_flags(tmp_path: Path) -> None:
    config = minimal_config()
    config["runtime"]["dev_env"] = {
        "enabled": True,
        "name": "dev",
        "shared_singleton_services": [
            "recall_rag",
            "searxng",
            "firecrawl",
            "google_workspace_mcp",
            "ms365_mcp",
        ],
    }
    config["feature_requests"] = {"pr": {"create_after_user_approval": False}}
    config_path = tmp_path / "config.yaml"
    out_dir = tmp_path / "runtime"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    subprocess.run(
        [sys.executable, str(CONFIG_COMPILER), "--config", str(config_path), "--output-dir", str(out_dir)],
        check=True,
    )
    env_text = (out_dir / "runtime.env").read_text(encoding="utf-8")
    assert "VIVENTIUM_DEV_ENV_ENABLED=true" in env_text
    assert "START_RAG_API=false" in env_text
    assert "START_SEARXNG=false" in env_text
    assert "START_FIRECRAWL=false" in env_text
    assert "START_GOOGLE_MCP=false" in env_text
    assert "START_MS365_MCP=false" in env_text
    assert "VIVENTIUM_SHARED_GOOGLE_MCP=true" in env_text
    assert "VIVENTIUM_SHARED_MS365_MCP=true" in env_text
    assert "VIVENTIUM_WORK_REQUEST_CREATE_PR_AFTER_USER_APPROVAL=false" in env_text
    assert "VIVENTIUM_FEATURE_REQUEST_CREATE_PR_AFTER_USER_APPROVAL=false" in env_text


def test_workflows_fail_loud_when_glasshive_host_workers_are_disabled(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "codex").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (fake_bin / "codex").chmod(0o755)
    app_support = tmp_path / "App Support" / "Viventium"
    runtime = app_support / "runtime"
    runtime.mkdir(parents=True)
    (runtime / "runtime.env").write_text(
        "START_GLASSHIVE=false\nGLASSHIVE_HOST_WORKERS_ENABLED=false\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

    proc = subprocess.run(
        [
            sys.executable,
            str(WORKFLOWS),
            "--repo-root",
            str(REPO_ROOT),
            "--app-support-dir",
            str(app_support),
            "--runtime-dir",
            str(runtime),
            "start",
            "heal",
            "--json",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert payload["state"] == "blocked"
    assert payload["failure_class"] == "glasshive_unavailable"
    assert (Path(payload["run_dir"]) / "01-rca-prompt.md").exists()
    workflow_prompt = (Path(payload["run_dir"]) / "00-heal-workflow.md").read_text(encoding="utf-8")
    assert "Write `01-rca.md`" in workflow_prompt
    assert "request orchestrator review" in workflow_prompt
    assert "write `03-proposed-fix.md`" in workflow_prompt
    assert "Only after both gates pass" in workflow_prompt
    assert "Do not push" in workflow_prompt


@pytest.mark.parametrize(
    "workflow_args",
    [
        ["heal"],
        ["feature-request", "--request", "Add update progress"],
        [
            "bug-report",
            "--what-happened",
            "The helper says update succeeded but the app stays stopped",
        ],
    ],
)
def test_workflows_allow_degraded_mode_is_explicit_and_private(
    tmp_path: Path, workflow_args: list[str]
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "codex").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (fake_bin / "codex").chmod(0o755)
    app_support = tmp_path / "App Support" / "Viventium"
    runtime = app_support / "runtime"
    runtime.mkdir(parents=True)
    (runtime / "runtime.env").write_text(
        "START_GLASSHIVE=false\nGLASSHIVE_HOST_WORKERS_ENABLED=false\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

    proc = subprocess.run(
        [
            sys.executable,
            str(WORKFLOWS),
            "--repo-root",
            str(REPO_ROOT),
            "--app-support-dir",
            str(app_support),
            "--runtime-dir",
            str(runtime),
            "start",
            *workflow_args,
            "--allow-degraded",
            "--json",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=True,
    )

    payload = json.loads(proc.stdout)
    assert payload["state"] == "degraded_ready"
    assert payload["failure_class"] == "glasshive_degraded_mode"
    assert "glasshive_project_id" not in payload
    assert "glasshive_worker_id" not in payload
    run_dir = Path(payload["run_dir"])
    assert run_dir.exists()
    assert run_dir.stat().st_mode & 0o777 == 0o700
    for artifact in run_dir.glob("*.md"):
        assert artifact.stat().st_mode & 0o777 == 0o600


def test_feature_request_workflow_records_pr_prompt_policy(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "codex").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (fake_bin / "codex").chmod(0o755)
    app_support = tmp_path / "App Support" / "Viventium"
    runtime = app_support / "runtime"
    runtime.mkdir(parents=True)
    (runtime / "runtime.env").write_text(
        "\n".join(
            [
                "START_GLASSHIVE=false",
                "GLASSHIVE_HOST_WORKERS_ENABLED=false",
                "VIVENTIUM_WORK_REQUEST_CREATE_PR_AFTER_USER_APPROVAL=false",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

    proc = subprocess.run(
        [
            sys.executable,
            str(WORKFLOWS),
            "--repo-root",
            str(REPO_ROOT),
            "--app-support-dir",
            str(app_support),
            "--runtime-dir",
            str(runtime),
            "start",
            "feature-request",
            "--request",
            "Add update progress",
            "--reasoning-effort",
            "xHigh",
            "--json",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert payload["reasoning_effort"] == "xhigh"
    assert payload["work_request_create_pr_after_user_approval"] is False
    assert payload["feature_request_create_pr_after_user_approval"] is False
    spec = (Path(payload["run_dir"]) / "feature-request.md").read_text(encoding="utf-8")
    assert "success criteria" in spec
    assert "Would you like me to create a feature request PR to Viventium?" in spec
    flow = (Path(payload["run_dir"]) / "00-feature-request-workflow.md").read_text(encoding="utf-8")
    assert "Stop for user approval before writing code" in flow
    assert "isolated feature worktree" in flow
    assert "Do not push" in flow


def test_bug_report_workflow_records_user_repro_intake(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "codex").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (fake_bin / "codex").chmod(0o755)
    app_support = tmp_path / "App Support" / "Viventium"
    runtime = app_support / "runtime"
    runtime.mkdir(parents=True)
    (runtime / "runtime.env").write_text(
        "\n".join(
            [
                "START_GLASSHIVE=false",
                "GLASSHIVE_HOST_WORKERS_ENABLED=false",
                "VIVENTIUM_WORK_REQUEST_CREATE_PR_AFTER_USER_APPROVAL=false",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

    proc = subprocess.run(
        [
            sys.executable,
            str(WORKFLOWS),
            "--repo-root",
            str(REPO_ROOT),
            "--app-support-dir",
            str(app_support),
            "--runtime-dir",
            str(runtime),
            "start",
            "bug-report",
            "--what-happened",
            "The helper says update succeeded but the app stays stopped",
            "--steps-to-reproduce",
            "Open helper > Advanced > Check for Updates > Install Update",
            "--expected",
            "The app restarts healthy",
            "--actual",
            "The helper still shows Stopped",
            "--details",
            "Started after a local helper rebuild",
            "--reasoning-effort",
            "xHigh",
            "--json",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert payload["workflow"] == "bug-report"
    assert payload["phase"] == "intake"
    assert payload["reasoning_effort"] == "xhigh"
    assert payload["work_request_create_pr_after_user_approval"] is False
    spec = (Path(payload["run_dir"]) / "bug-report.md").read_text(encoding="utf-8")
    assert "The helper says update succeeded" in spec
    assert "Steps To Reproduce" in spec
    assert "Expected Behavior" in spec
    assert "Actual Behavior" in spec
    assert "missing reproduction details" in spec
    assert "Evidence To Inspect" in spec
    assert "Impacted Surfaces" in spec
    assert "QA Acceptance" in spec
    assert "Would you like me to create a bug fix PR to Viventium?" in spec
    flow = (Path(payload["run_dir"]) / "00-bug-report-workflow.md").read_text(encoding="utf-8")
    assert "Stop for user approval before writing code" in flow
    assert "isolated bugfix worktree" in flow
    assert "Do not push" in flow


def test_heal_apply_mode_creates_isolated_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    (repo / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "init"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
    )

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "codex").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (fake_bin / "codex").chmod(0o755)
    app_support = tmp_path / "App Support" / "Viventium"
    runtime = app_support / "runtime"
    runtime.mkdir(parents=True)
    (runtime / "runtime.env").write_text(
        "START_GLASSHIVE=false\nGLASSHIVE_HOST_WORKERS_ENABLED=false\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

    proc = subprocess.run(
        [
            sys.executable,
            str(WORKFLOWS),
            "--repo-root",
            str(repo),
            "--app-support-dir",
            str(app_support),
            "--runtime-dir",
            str(runtime),
            "start",
            "heal",
            "--mode",
            "apply",
            "--json",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert payload["state"] == "blocked"
    assert payload["workflow_branch"].startswith("heal/")
    worktree = Path(payload["isolated_worktree"])
    assert worktree.exists()
    assert worktree != repo
    implementation_prompt = (Path(payload["run_dir"]) / "05-implementation-prompt.md").read_text(encoding="utf-8")
    assert str(worktree) in implementation_prompt

    cancel = subprocess.run(
        [
            sys.executable,
            str(WORKFLOWS),
            "--repo-root",
            str(repo),
            "--app-support-dir",
            str(app_support),
            "--runtime-dir",
            str(runtime),
            "cancel",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=True,
    )
    assert "Cancelled workflow" in cancel.stdout
    assert not worktree.exists()
    branches = subprocess.run(["git", "branch", "--list", payload["workflow_branch"]], cwd=repo, text=True, stdout=subprocess.PIPE, check=True)
    assert branches.stdout.strip() == ""


def test_feature_request_approval_creates_isolated_feature_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    (repo / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "init"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
    )

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "codex").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (fake_bin / "codex").chmod(0o755)
    app_support = tmp_path / "App Support" / "Viventium"
    runtime = app_support / "runtime"
    runtime.mkdir(parents=True)
    (runtime / "runtime.env").write_text(
        "START_GLASSHIVE=false\nGLASSHIVE_HOST_WORKERS_ENABLED=false\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

    start = subprocess.run(
        [
            sys.executable,
            str(WORKFLOWS),
            "--repo-root",
            str(repo),
            "--app-support-dir",
            str(app_support),
            "--runtime-dir",
            str(runtime),
            "start",
            "feature-request",
            "--request",
            "Add update progress",
            "--json",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    assert start.returncode == 2

    approve = subprocess.run(
        [
            sys.executable,
            str(WORKFLOWS),
            "--repo-root",
            str(repo),
            "--app-support-dir",
            str(app_support),
            "--runtime-dir",
            str(runtime),
            "approve",
            "--slug",
            "update-progress",
            "--json",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    assert approve.returncode == 2
    payload = json.loads(approve.stdout)
    assert payload["phase"] == "implementation"
    assert payload["workflow_branch"].startswith("feature/update-progress")
    worktree = Path(payload["isolated_worktree"])
    assert worktree.exists()
    implementation_prompt = (Path(payload["run_dir"]) / "03-approved-implementation-prompt.md").read_text(encoding="utf-8")
    assert str(worktree) in implementation_prompt
    assert "Do not push or create a remote PR" in implementation_prompt


def test_bug_report_approval_creates_isolated_bugfix_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    (repo / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "init"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
    )

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "codex").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (fake_bin / "codex").chmod(0o755)
    app_support = tmp_path / "App Support" / "Viventium"
    runtime = app_support / "runtime"
    runtime.mkdir(parents=True)
    (runtime / "runtime.env").write_text(
        "START_GLASSHIVE=false\nGLASSHIVE_HOST_WORKERS_ENABLED=false\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

    start = subprocess.run(
        [
            sys.executable,
            str(WORKFLOWS),
            "--repo-root",
            str(repo),
            "--app-support-dir",
            str(app_support),
            "--runtime-dir",
            str(runtime),
            "start",
            "bug-report",
            "--what-happened",
            "Update modal closes but the helper remains stopped",
            "--json",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    assert start.returncode == 2

    approve = subprocess.run(
        [
            sys.executable,
            str(WORKFLOWS),
            "--repo-root",
            str(repo),
            "--app-support-dir",
            str(app_support),
            "--runtime-dir",
            str(runtime),
            "approve",
            "--slug",
            "update-modal-stopped",
            "--json",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    assert approve.returncode == 2
    payload = json.loads(approve.stdout)
    assert payload["phase"] == "implementation"
    assert payload["workflow_branch"].startswith("bugfix/update-modal-stopped")
    worktree = Path(payload["isolated_worktree"])
    assert worktree.exists()
    implementation_prompt = (Path(payload["run_dir"]) / "07-approved-bugfix-prompt.md").read_text(encoding="utf-8")
    assert str(worktree) in implementation_prompt
    assert "Reproduce or validate the bug" in implementation_prompt
    assert "Do not push or create a remote PR" in implementation_prompt

    cancel = subprocess.run(
        [
            sys.executable,
            str(WORKFLOWS),
            "--repo-root",
            str(repo),
            "--app-support-dir",
            str(app_support),
            "--runtime-dir",
            str(runtime),
            "cancel",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=True,
    )
    assert "Cancelled workflow" in cancel.stdout
    assert not worktree.exists()
    branches = subprocess.run(["git", "branch", "--list", payload["workflow_branch"]], cwd=repo, text=True, stdout=subprocess.PIPE, check=True)
    assert branches.stdout.strip() == ""


def test_workflows_dispatch_glasshive_host_worker_with_bootstrap_content(tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
            if self.path == "/health":
                self._send(200, {"ok": True})
                return
            if self.path in {"/v1/metrics", "/v1/metrics/summary"}:
                self._send(404, {"error": "not found"})
                return
            self._send(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802 - stdlib callback name
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body or "{}")
            captured[self.path] = payload
            if self.path == "/v1/projects":
                self._send(201, {"project_id": "project-test"})
                return
            if self.path == "/v1/projects/project-test/workers/find-or-resume":
                self._send(200, {"worker_id": "worker-test"})
                return
            if self.path == "/v1/workers/worker-test/assign":
                self._send(202, {"run_id": "glasshive-run-test"})
                return
            if self.path == "/v1/workers/worker-test/interrupt":
                captured[self.path] = payload
                self._send(202, {"worker_id": "worker-test", "state": "idle"})
                return
            self._send(404, {"error": "not found"})

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        (fake_bin / "codex").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        (fake_bin / "codex").chmod(0o755)
        app_support = tmp_path / "App Support" / "Viventium"
        runtime = app_support / "runtime"
        runtime.mkdir(parents=True)
        (runtime / "runtime.env").write_text(
            "\n".join(
                [
                    "START_GLASSHIVE=true",
                    "GLASSHIVE_HOST_WORKERS_ENABLED=true",
                    f"WPR_MCP_BASE_URL=http://127.0.0.1:{server.server_port}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

        proc = subprocess.run(
            [
                sys.executable,
                str(WORKFLOWS),
                "--repo-root",
                str(REPO_ROOT),
                "--app-support-dir",
                str(app_support),
                "--runtime-dir",
                str(runtime),
                "start",
                "heal",
                "--json",
            ],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        cancel_proc = subprocess.run(
            [
                sys.executable,
                str(WORKFLOWS),
                "--repo-root",
                str(REPO_ROOT),
                "--app-support-dir",
                str(app_support),
                "--runtime-dir",
                str(runtime),
                "cancel",
            ],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
    finally:
        server.shutdown()
        server.server_close()

    summary = json.loads(proc.stdout)
    assert summary["state"] == "running"
    worker_payload = captured["/v1/projects/project-test/workers/find-or-resume"]
    assert isinstance(worker_payload, dict)
    assert worker_payload["execution_mode"] == "host"
    assert worker_payload["profile"] == "codex-cli"
    bundle = worker_payload["bootstrap_bundle"]
    assert isinstance(bundle, dict)
    files = bundle["files"]
    assert isinstance(files, list)
    first_file = files[0]
    assert "content" in first_file
    assert "text" not in first_file
    assignment = captured["/v1/workers/worker-test/assign"]
    assert isinstance(assignment, dict)
    assert "Write `01-rca.md`" in assignment["instruction"]
    assert "Only after both gates pass" in assignment["instruction"]
    assert captured["/v1/workers/worker-test/interrupt"] == {}
    assert "Cancelled workflow" in cancel_proc.stdout


def test_upgrade_check_uses_helper_package_hash_contract(tmp_path: Path) -> None:
    app_support = tmp_path / "App Support" / "Viventium"
    app_support.mkdir(parents=True)

    proc = subprocess.run(
        [
            sys.executable,
            str(UPGRADE_CHECK),
            "--repo-root",
            str(REPO_ROOT),
            "--app-support-dir",
            str(app_support),
            "--no-fetch",
            "--json",
        ],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    payload = json.loads(proc.stdout)
    assert payload["helper_needs_rebuild"] is False


def test_upgrade_check_blocks_on_helper_rebuild_need(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    helper = repo / "apps" / "macos" / "ViventiumHelper"
    source = helper / "Sources" / "ViventiumHelper" / "ViventiumHelperApp.swift"
    plist = helper / "Sources" / "ViventiumHelper" / "Resources" / "Info.plist"
    hash_file = helper / "prebuilt" / "source.sha256"
    source.parent.mkdir(parents=True)
    plist.parent.mkdir(parents=True)
    hash_file.parent.mkdir(parents=True)
    (helper / "Package.swift").write_text("// package\n", encoding="utf-8")
    source.write_text("print(\"changed\")\n", encoding="utf-8")
    plist.write_text("<plist />\n", encoding="utf-8")
    hash_file.write_text("not-current\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "init"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
    )
    app_support = tmp_path / "App Support" / "Viventium"
    app_support.mkdir(parents=True)

    proc = subprocess.run(
        [
            sys.executable,
            str(UPGRADE_CHECK),
            "--repo-root",
            str(repo),
            "--app-support-dir",
            str(app_support),
            "--no-fetch",
            "--json",
        ],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    payload = json.loads(proc.stdout)
    assert payload["helper_needs_rebuild"] is True
    assert "helper_rebuild_needed" in payload["blockers"]


def test_password_reset_link_script_closes_mongo_connection() -> None:
    source = PASSWORD_RESET_LINK_SCRIPT.read_text(encoding="utf-8")
    assert "const mongoose = require('mongoose');" in source
    assert "await mongoose.disconnect();" in source


def test_cli_registers_new_commands_and_reexec_contract() -> None:
    source = BIN_VIVENTIUM.read_text(encoding="utf-8")
    for command in [
        "dev-env",
        "dev-runtime",
        "workflows",
        "heal",
        "feature-request",
        "report-bug",
        "bug-report",
    ]:
        assert f"  {command}" in source
    reexec_section = source.split("maybe_reexec_active_runtime_checkout() {", 1)[1].split(
        "yaml_file_has_unique_mapping_keys()",
        1,
    )[0]
    assert "workflows|heal|feature-request|report-bug|bug-report" in reexec_section
    assert "dev-runtime" not in reexec_section


def test_report_bug_command_reexecs_active_runtime_checkout(tmp_path: Path) -> None:
    app_support = tmp_path / "App Support" / "Viventium"
    active_repo = tmp_path / "active-viventium"
    (active_repo / "bin").mkdir(parents=True)
    (active_repo / "scripts" / "viventium").mkdir(parents=True)
    (active_repo / "viventium_v0_4").mkdir(parents=True)
    (active_repo / "scripts" / "viventium" / "common.sh").write_text("# fake common\n", encoding="utf-8")
    (active_repo / "viventium_v0_4" / "viventium-librechat-start.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    fake_bin = active_repo / "bin" / "viventium"
    fake_bin.write_text("#!/bin/sh\necho ACTIVE_REPORT_BUG_REEXEC \"$@\"\n", encoding="utf-8")
    fake_bin.chmod(0o755)
    state = app_support / "state"
    state.mkdir(parents=True)
    (state / "active-checkout.json").write_text(json.dumps({"repoRoot": str(active_repo)}) + "\n", encoding="utf-8")

    proc = subprocess.run(
        [str(BIN_VIVENTIUM), "--app-support-dir", str(app_support), "report-bug", "status"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    assert "ACTIVE_REPORT_BUG_REEXEC" in proc.stdout
    assert "report-bug status" in proc.stdout

    alias_proc = subprocess.run(
        [str(BIN_VIVENTIUM), "--app-support-dir", str(app_support), "bug-report", "status"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    assert "ACTIVE_REPORT_BUG_REEXEC" in alias_proc.stdout
    assert "bug-report status" in alias_proc.stdout


def test_helper_exposes_update_heal_and_feature_request_actions() -> None:
    source = HELPER_SOURCE.read_text(encoding="utf-8")
    assert "Check for Updates..." in source
    assert "Heal Viventium..." in source
    assert "Report a Bug..." in source
    assert "Request a Feature..." in source
    assert "Approve Build or Fix..." in source
    assert "Cancel Active Workflow" in source
    assert "Open Work Artifacts" in source
    assert "Start Viventium at Login" in source
    assert "Show Status Bar Icon" in source
    assert ".help(" in source
    assert "Heal Settings" in source
    assert "What happened?" in source
    assert "Steps to reproduce" in source
    assert "Auto (Codex preferred)" in source
    assert '"xHigh"' in source
    assert '"--provider"' in source
    assert '"report-bug"' in source
    assert '"--what-happened"' in source
    assert "workflowStatusLabel" in source
    assert "menuGlyph" in source
    assert '"V*"' in source
    assert "Building Feature" in source
    assert "Bug Intake" in source
    assert "Bug Report Ready" in source
    assert "Fixing Bug" in source
    assert "Feature Intake" in source
    assert "Feature Ready" in source
    assert "Healing (" in source


def test_helper_lifecycle_qa_uses_localhost_health_probes() -> None:
    source = HELPER_LIFECYCLE_QA.read_text(encoding="utf-8")
    assert '"api": ("http://localhost:3180/api/health", {200})' in source
    assert '"web": ("http://localhost:3190/", {200})' in source
    assert '"playground": ("http://localhost:3300/", {200})' in source
    assert "http://127.0.0.1:3180" not in source
    assert "http://127.0.0.1:3190" not in source
    assert "http://127.0.0.1:3300" not in source


def test_helper_lifecycle_qa_help_does_not_require_pyobjc_bridge() -> None:
    proc = subprocess.run(
        [sys.executable, str(HELPER_LIFECYCLE_QA), "--help"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    assert "Drive the installed ViventiumHelper menu" in proc.stdout


def test_helper_keeps_workflow_and_maintenance_actions_under_advanced_menu() -> None:
    source = HELPER_SOURCE.read_text(encoding="utf-8")
    menu_body = source.split("MenuBarExtra(", 1)[1].split("} label:", 1)[0]
    top_level_before_advanced = menu_body.split('Menu("Advanced") {', 1)[0]
    advanced_menu = menu_body.split('Menu("Advanced") {', 1)[1].split('Button("Quit") {', 1)[0]

    for top_level_label in [
        'Button("Open")',
        "Button(self.controller.actionLabel)",
        "Button(self.controller.statusLabel)",
        'Menu("Advanced")',
    ]:
        assert top_level_label in menu_body

    for advanced_only in [
        'Button("Check for Updates...")',
        "Button(self.controller.backupActionLabel)",
        'Button("Heal Viventium...")',
        'Button("Report a Bug...")',
        'Button("Request a Feature...")',
        'Button("Approve Build or Fix...")',
        'Button("Cancel Active Workflow")',
        'Button("Open Work Artifacts")',
        'Toggle(\n                    "Start Viventium at Login"',
        'Toggle(\n                    "Show Status Bar Icon"',
    ]:
        assert advanced_only in advanced_menu
        assert advanced_only not in top_level_before_advanced
