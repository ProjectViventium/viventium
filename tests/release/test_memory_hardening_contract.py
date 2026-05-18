from __future__ import annotations

import importlib.util
import plistlib
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG_COMPILER_SPEC = importlib.util.spec_from_file_location(
    "viventium_config_compiler",
    ROOT / "scripts/viventium/config_compiler.py",
)
assert CONFIG_COMPILER_SPEC and CONFIG_COMPILER_SPEC.loader
config_compiler = importlib.util.module_from_spec(CONFIG_COMPILER_SPEC)
CONFIG_COMPILER_SPEC.loader.exec_module(config_compiler)

MEMORY_HARDEN_SPEC = importlib.util.spec_from_file_location(
    "viventium_memory_harden",
    ROOT / "scripts/viventium/memory_harden.py",
)
assert MEMORY_HARDEN_SPEC and MEMORY_HARDEN_SPEC.loader
memory_harden = importlib.util.module_from_spec(MEMORY_HARDEN_SPEC)
MEMORY_HARDEN_SPEC.loader.exec_module(memory_harden)


def test_memory_hardening_defaults_are_launch_ready_and_opt_in() -> None:
    settings = config_compiler.resolve_memory_hardening_settings({})

    assert settings["enabled"] is False
    assert settings["schedule"] == "0 3 * * *"
    assert settings["lookback_days"] == 7
    assert settings["min_user_idle_minutes"] == 60
    assert settings["max_changes_per_user"] == 3
    assert settings["max_input_chars"] == 500000
    assert settings["require_full_lookback"] is True
    assert settings["provider_profile"] == "launch_ready_only"
    assert settings["anthropic_model"] in config_compiler.MEMORY_HARDENING_LAUNCH_READY_MODELS["anthropic"]
    assert settings["openai_model"] in config_compiler.MEMORY_HARDENING_LAUNCH_READY_MODELS["openai"]
    assert settings["anthropic_effort"] == "xhigh"
    assert settings["openai_reasoning_effort"] == "xhigh"
    assert settings["transcripts"]["rag_mode"] == "detailed_summary_only"


def test_memory_hardening_wrapper_passes_compiled_model_tuple() -> None:
    class Args:
        repo_root = ROOT
        app_support_dir = ROOT / ".tmp-app-support"
        runtime_dir = ROOT / ".tmp-runtime"
        command = "dry-run"
        mongo_uri = None
        config_path = None
        run_id = None
        user_email = None
        user_id = None
        lookback_days = None
        min_user_idle_minutes = None
        max_changes_per_user = None
        max_input_chars = None
        provider = None
        model = None
        proposal_file = None
        allow_delete = False
        ignore_idle_gate = False
        skip_model_probe = False
        allow_partial_lookback = False
        json = False

    command = memory_harden.node_command(
        Args(),
        {
            "VIVENTIUM_MEMORY_HARDENING_PROVIDER": "openai",
            "VIVENTIUM_MEMORY_HARDENING_MODEL": "gpt-5.5",
            "VIVENTIUM_MEMORY_HARDENING_USER_EMAIL": "qa@example.com",
            "VIVENTIUM_MEMORY_TRANSCRIPTS_RAG_MODE": "detailed_summary_only",
        },
    )

    assert command[command.index("--provider") + 1] == "openai"
    assert command[command.index("--model") + 1] == "gpt-5.5"
    assert command[command.index("--user-email") + 1] == "qa@example.com"
    assert command[command.index("--transcript-rag-mode") + 1] == "detailed_summary_only"


def test_memory_hardening_wrapper_loads_canonical_runtime_env_stack(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    librechat_dir = tmp_path / "LibreChat"
    service_env_dir = runtime_dir / "service-env"
    service_env_dir.mkdir(parents=True)
    librechat_dir.mkdir(parents=True)

    (librechat_dir / ".env").write_text(
        "MONGO_URI=mongodb://legacy-repo\n"
        "LEGACY_ONLY=repo\n",
        encoding="utf-8",
    )
    (runtime_dir / "local.env").write_text(
        "MONGO_URI=mongodb://legacy-local\n"
        "LEGACY_LOCAL=1\n",
        encoding="utf-8",
    )
    (runtime_dir / "librechat.env").write_text(
        "CONFIG_PATH=/legacy/librechat.yaml\n",
        encoding="utf-8",
    )
    (runtime_dir / "runtime.env").write_text(
        "MONGO_URI=mongodb://runtime\n"
        "CONFIG_PATH=/runtime/librechat.yaml\n"
        "VIVENTIUM_MEMORY_HARDENING_PROVIDER=anthropic\n",
        encoding="utf-8",
    )
    (runtime_dir / "runtime.local.env").write_text(
        "MONGO_URI=mongodb://runtime-local\n"
        "LOCAL_ONLY=1\n",
        encoding="utf-8",
    )
    (service_env_dir / "librechat.env").write_text(
        "CONFIG_PATH=/service/librechat.yaml\n"
        "MONGO_URI=''\n"
        "SERVICE_ONLY=1\n",
        encoding="utf-8",
    )

    env = memory_harden.load_runtime_env(runtime_dir, librechat_dir)

    assert [path.relative_to(tmp_path).as_posix() for path in memory_harden.runtime_env_candidates(runtime_dir, librechat_dir)] == [
        "LibreChat/.env",
        "runtime/local.env",
        "runtime/librechat.env",
        "runtime/runtime.env",
        "runtime/runtime.local.env",
        "runtime/service-env/librechat.env",
    ]
    assert env["MONGO_URI"] == "mongodb://runtime-local"
    assert env["CONFIG_PATH"] == "/service/librechat.yaml"
    assert env["LEGACY_ONLY"] == "repo"
    assert env["LEGACY_LOCAL"] == "1"
    assert env["LOCAL_ONLY"] == "1"
    assert env["SERVICE_ONLY"] == "1"


def test_memory_hardening_wrapper_prefers_compiled_runtime_over_ambient_shell_env(
    monkeypatch, tmp_path: Path
) -> None:
    class Args:
        repo_root = ROOT
        command = "status"
        mongo_uri = None
        config_path = None
        run_id = None
        user_email = None
        user_id = None
        lookback_days = None
        min_user_idle_minutes = None
        max_changes_per_user = None
        max_input_chars = None
        provider = None
        model = None
        proposal_file = None
        transcripts_dir = None
        transcript_max_files_per_run = None
        transcript_max_chars_per_file = None
        transcript_summary_max_chars = None
        transcript_rag_mode = None
        allow_delete = False
        ignore_idle_gate = False
        skip_model_probe = False
        allow_partial_lookback = False
        scheduled = False
        json = False

    Args.app_support_dir = tmp_path / "app-support"
    Args.runtime_dir = tmp_path / "app-support" / "runtime"

    class Completed:
        returncode = 0

    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return Completed()

    monkeypatch.setenv("RAG_API_URL", "http://stale-shell-rag")
    monkeypatch.setattr(memory_harden.subprocess, "run", fake_run)

    status = memory_harden.run_node(
        Args(),
        {
            "RAG_API_URL": "http://compiled-rag",
            "VIVENTIUM_MEMORY_HARDENING_PROVIDER": "anthropic",
            "VIVENTIUM_MEMORY_HARDENING_MODEL": "claude-opus-4-7",
        },
    )

    assert status == 0
    assert calls[0][1]["env"]["RAG_API_URL"] == "http://compiled-rag"


def test_memory_hardening_wrapper_uses_provider_specific_model_for_override() -> None:
    class Args:
        repo_root = ROOT
        app_support_dir = ROOT / ".tmp-app-support"
        runtime_dir = ROOT / ".tmp-runtime"
        command = "dry-run"
        mongo_uri = None
        config_path = None
        run_id = None
        user_email = None
        user_id = None
        lookback_days = None
        min_user_idle_minutes = None
        max_changes_per_user = None
        max_input_chars = None
        provider = "openai"
        model = None
        proposal_file = None
        allow_delete = False
        ignore_idle_gate = False
        skip_model_probe = False
        allow_partial_lookback = False
        json = False

    command = memory_harden.node_command(
        Args(),
        {
            "VIVENTIUM_MEMORY_HARDENING_PROVIDER": "anthropic",
            "VIVENTIUM_MEMORY_HARDENING_MODEL": "claude-opus-4-7",
            "VIVENTIUM_MEMORY_HARDENING_OPENAI_MODEL": "gpt-5.5",
        },
    )

    assert command[command.index("--provider") + 1] == "openai"
    assert command[command.index("--model") + 1] == "gpt-5.5"


def test_memory_hardening_cli_user_email_overrides_compiled_operator_scope() -> None:
    class Args:
        repo_root = ROOT
        app_support_dir = ROOT / ".tmp-app-support"
        runtime_dir = ROOT / ".tmp-runtime"
        command = "dry-run"
        mongo_uri = None
        config_path = None
        run_id = None
        user_email = "explicit@example.com"
        user_id = None
        lookback_days = None
        min_user_idle_minutes = None
        max_changes_per_user = None
        max_input_chars = None
        provider = None
        model = None
        proposal_file = None
        allow_delete = False
        ignore_idle_gate = False
        skip_model_probe = False
        allow_partial_lookback = False
        json = False

    command = memory_harden.node_command(
        Args(),
        {
            "VIVENTIUM_MEMORY_HARDENING_PROVIDER": "anthropic",
            "VIVENTIUM_MEMORY_HARDENING_MODEL": "claude-opus-4-7",
            "VIVENTIUM_MEMORY_HARDENING_USER_EMAIL": "compiled@example.com",
        },
    )

    assert command[command.index("--user-email") + 1] == "explicit@example.com"


def test_memory_hardening_schedule_runs_wrapper_directly_without_cli_lock(tmp_path, monkeypatch) -> None:
    plist_path = tmp_path / "ai.viventium.memory-harden.plist"
    app_support_dir = tmp_path / "app-support"
    runtime_dir = app_support_dir / "runtime"

    class Args:
        pass

    args = Args()
    args.repo_root = ROOT
    args.app_support_dir = app_support_dir
    args.runtime_dir = runtime_dir
    args.schedule = None
    args.user_email = None

    class Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    launchctl_calls = []

    def fake_run(command, **kwargs):
        launchctl_calls.append(command)
        return Completed()

    monkeypatch.setattr(memory_harden, "launch_agent_path", lambda: plist_path)
    monkeypatch.setattr(memory_harden.subprocess, "run", fake_run)
    monkeypatch.setattr(memory_harden.sys, "platform", "darwin")

    result = memory_harden.install_schedule(
        args,
        {
            "VIVENTIUM_MEMORY_HARDENING_SCHEDULE": "0 3 * * *",
            "VIVENTIUM_MEMORY_HARDENING_USER_EMAIL": "qa@example.com",
        },
    )
    payload = plistlib.loads(plist_path.read_bytes())
    scheduled_command = payload["ProgramArguments"][-1]

    assert result["schedule"] == "0 3 * * *"
    assert payload["StartCalendarInterval"] == {"Hour": 3, "Minute": 0}
    assert payload["WorkingDirectory"] == str(app_support_dir)
    assert not scheduled_command.startswith("cd ")
    assert "/usr/bin/env -i" in scheduled_command
    assert f"PATH={Path.home()}/.local/bin:{Path.home()}/.codex/bin:" in scheduled_command
    assert "/Applications/Codex.app/Contents/Resources" in scheduled_command
    assert "/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" in scheduled_command
    assert "bin/viventium" not in scheduled_command
    assert "scripts/viventium/memory_harden.py" in scheduled_command
    assert "--runtime-dir" in scheduled_command
    assert "--user-email qa@example.com" in scheduled_command
    assert "apply --scheduled" in scheduled_command
    assert launchctl_calls[-1][0:2] == ["launchctl", "bootstrap"]


def test_memory_hardening_cli_reexecs_active_runtime_checkout() -> None:
    text = (ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    reexec_section = text.split("maybe_reexec_active_runtime_checkout() {", 1)[1].split(
        "yaml_file_has_unique_mapping_keys()",
        1,
    )[0]

    for command in [
        "start",
        "launch",
        "stop",
        "install-helper",
        "uninstall-helper",
        "status-bar",
        "memory-harden",
    ]:
        assert command in reexec_section


def test_scheduled_transcript_ingest_honors_dry_run_first_marker(tmp_path, monkeypatch) -> None:
    class Args:
        repo_root = ROOT
        command = "ingest-transcripts"
        apply = True
        mongo_uri = None
        config_path = None
        run_id = None
        user_email = None
        user_id = None
        lookback_days = None
        min_user_idle_minutes = None
        max_changes_per_user = None
        max_input_chars = None
        provider = None
        model = None
        proposal_file = None
        transcripts_dir = None
        transcript_max_files_per_run = None
        transcript_max_chars_per_file = None
        transcript_summary_max_chars = None
        transcript_rag_mode = None
        allow_delete = False
        ignore_idle_gate = False
        skip_model_probe = False
        allow_partial_lookback = False
        scheduled = True
        json = False

    Args.app_support_dir = tmp_path / "app-support"
    Args.runtime_dir = tmp_path / "app-support" / "runtime"

    class Completed:
        returncode = 0

    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return Completed()

    monkeypatch.setattr(memory_harden.subprocess, "run", fake_run)

    status = memory_harden.run_node(
        Args(),
        {
            "VIVENTIUM_MEMORY_HARDENING_PROVIDER": "anthropic",
            "VIVENTIUM_MEMORY_HARDENING_MODEL": "claude-opus-4-7",
            "VIVENTIUM_MEMORY_HARDENING_DRY_RUN_FIRST": "true",
        },
    )

    marker = Args.app_support_dir / "state" / "memory-hardening" / "dry-run-first-complete"
    assert status == 0
    assert marker.exists()
    assert calls and calls[0][calls[0].index("--mode") + 1] == "dry-run"
    assert "--transcripts-only" in calls[0]


def test_memory_hardening_public_audit_contract_has_no_raw_path_field() -> None:
    script = ROOT / "viventium_v0_4" / "LibreChat" / "scripts" / "viventium-memory-hardening.js"
    text = script.read_text(encoding="utf-8")

    assert "raw_proposal_path" not in text
    assert "private_proposal_file" in text
    assert re.search(r"proposal\.private\.json", text)
    assert re.search(r"rollback\.private\.json", text)


def test_memory_hardening_treats_listen_only_as_soft_transcript_evidence() -> None:
    script = ROOT / "viventium_v0_4" / "LibreChat" / "scripts" / "viventium-memory-hardening.js"
    text = script.read_text(encoding="utf-8")

    assert "type === 'listen_only_transcript'" in text
    assert "role \"ambient_transcript\"" in text
    assert "stable_memory_requires_corroborated_listen_only_evidence" in text
    assert "listenOnlyConversationSourceIds" in text


def test_memory_hardening_docs_keep_private_artifacts_out_of_public_qa() -> None:
    boundary_doc = ROOT / "docs/requirements_and_learnings/40_Public_Private_Boundaries_and_License_Matrix.md"
    qa_readme = ROOT / "qa/memory-hardening/README.md"

    boundary_text = boundary_doc.read_text(encoding="utf-8")
    qa_text = qa_readme.read_text(encoding="utf-8")

    assert "proposal.private.json" in boundary_text
    assert "rollback.private.json" in boundary_text
    assert "Raw proposals and rollback snapshots stay under local App Support state" in qa_text


def test_meeting_transcript_eval_fixtures_are_executable() -> None:
    subprocess.run(
        [sys.executable, "-c", "import shutil, sys; sys.exit(0 if shutil.which('node') else 1)"],
        check=True,
    )
    subprocess.run(
        ["node", str(ROOT / "qa/meeting-transcript-memory/evals/run-evals.cjs")],
        check=True,
        cwd=ROOT,
    )


def test_meeting_transcript_recall_dist_bundle_contains_runtime_hooks() -> None:
    dist = ROOT / "viventium_v0_4" / "LibreChat" / "packages" / "api" / "dist" / "index.js"
    text = dist.read_text(encoding="utf-8")

    assert "viventiumMeetingTranscriptRecall: true" in text
    assert "FileContext.meeting_transcript" in text
    assert "metadata.meetingTranscriptSourcePathHash" in text
    assert "metadata.meetingTranscriptKind" in text
    assert "Meeting transcript recall configured but no artifacts for active user" in text
