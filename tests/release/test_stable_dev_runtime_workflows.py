from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import signal
import shlex
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
INSTALL_SUMMARY = REPO_ROOT / "scripts" / "viventium" / "install_summary.py"
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
FULL_STACK_LAUNCHER = REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"


def extract_shell_function(source: str, name: str) -> str:
    start = source.index(f"{name}() {{")
    collected: list[str] = []
    depth = 0
    for line in source[start:].splitlines():
        collected.append(line)
        depth += line.count("{")
        depth -= line.count("}")
        if depth == 0:
            break
    return "\n".join(collected) + "\n"


def minimal_config() -> dict:
    return {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "profile": "isolated",
            "ports": {
                "lc_api_port": 3180,
                "lc_frontend_port": 3190,
                "sandpack_bundler_port": 3191,
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
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "synthetic-groq-test-key",
            },
            "primary": {"provider": "openai", "auth_mode": "connected_account"},
            "secondary": {
                "provider": "anthropic",
                "auth_mode": "api_key",
                "secret_value": "synthetic-anthropic-test-key",
            },
        },
        "voice": {"mode": "local", "stt_provider": "whisper_local", "tts_provider": "browser"},
        "integrations": {
            "web_search": {"enabled": True, "search_provider": "searxng", "scraper_provider": "firecrawl"},
            "google_workspace": {"enabled": True},
            "ms365": {"enabled": True},
            "glasshive": {"enabled": False},
        },
    }


def test_dev_runtime_validation_fails_closed_before_restart() -> None:
    source = BIN_VIVENTIUM.read_text(encoding="utf-8")
    activation = source[source.index("dev_runtime_command() {") : source.index("workflows_command() {")]

    compile_invocation = '"$PYTHON_BIN" "$REPO_ROOT/scripts/viventium/config_compiler.py"'
    compile_guard = 'if [[ "$compiler_status" != "0" ]]; then'
    doctor_guard = 'if ! "$REPO_ROOT/scripts/viventium/doctor.sh" \\\n'
    artifact_guard = '! "$PYTHON_BIN" "$REPO_ROOT/scripts/viventium/helper_artifact_verify.py"'
    stop_gate = "dev_runtime_activation_tool quiesce-helper"
    helper_process_gate = "quiesce_macos_helper_process_for_activation"
    telegram_migration_gate = 'migrate_telegram_user_configs "$previous_repo"'
    telegram_recovery_publish_gate = (
        'publish_active_telegram_recovery_component \\\n'
        '        "dev-runtime-activation" "$activation_dir"'
    )
    telegram_helper_arm_gate = "arm_persistent_telegram_recovery_helper"
    begin_gate = "dev_runtime_activation_tool begin-new"
    publish_gate = "if ! dev_runtime_activation_tool publish"
    commit_gate = "if ! dev_runtime_activation_tool commit"
    helper_guard = 'if ! runtime_checkout_refresh_helper; then'
    helper_receipt = "if ! dev_runtime_activation_tool finalize-helper"
    restart_gate = 'if [[ "$restart" == "1" ]]; then'
    component_bootstrap = "bootstrap_components --prefer-existing-checkout-head"
    strict_component_validation = "bootstrap_components --validate-only --strict-pinned"
    config_digest_flag = "--expected-config-sha256"
    app_support_gate = 'ensure_app_support_layout "$APP_SUPPORT_DIR"'
    assert compile_guard in activation
    assert doctor_guard in activation
    assert artifact_guard in activation
    assert begin_gate in activation
    assert helper_guard in activation
    assert "binding, live runtime, helper, and running state were not changed" in activation
    assert "restore_previous_dev_runtime_after_failure" in activation
    assert component_bootstrap in activation
    assert strict_component_validation in activation
    assert config_digest_flag in activation
    assert activation.count("ensure_local_checkout_alignment") >= 2
    first_alignment = activation.index("ensure_local_checkout_alignment")
    second_alignment = activation.index(
        "ensure_local_checkout_alignment",
        first_alignment + 1,
    )
    assert first_alignment < activation.index(component_bootstrap)
    assert activation.index(component_bootstrap) < activation.index(strict_component_validation)
    assert activation.index(strict_component_validation) < second_alignment
    assert second_alignment < activation.index(app_support_gate)
    assert activation.index(app_support_gate) < activation.index(begin_gate)
    assert activation.index(compile_invocation) < activation.index(compile_guard)
    assert activation.index(compile_guard) < activation.index(doctor_guard)
    assert activation.index(doctor_guard) < activation.index(artifact_guard)
    assert activation.index(begin_gate) < activation.index(helper_process_gate)
    assert activation.index(helper_process_gate) < activation.index(stop_gate)
    assert activation.index(helper_process_gate) < activation.index(compile_guard)
    assert (
        activation.index(telegram_migration_gate)
        < activation.index(
            telegram_recovery_publish_gate,
            activation.index(telegram_migration_gate),
        )
        < activation.index(telegram_helper_arm_gate)
        < activation.index(publish_gate)
    )
    assert "rollback_prepared_dev_runtime_activation" in activation
    assert "mktemp -d" not in activation
    assert activation.index(artifact_guard) < activation.index(publish_gate)
    assert activation.index(publish_gate) < activation.index(restart_gate)
    assert activation.index(restart_gate) < activation.index(commit_gate)
    assert (
        activation.index(commit_gate)
        < activation.index("dev_runtime_activation_tool commit", activation.index(commit_gate))
    )
    assert (
        "VIVENTIUM_PRESERVE_HELPER_RUNTIME_INTENT=1 \\\n"
        "          VIVENTIUM_DEV_RUNTIME_RECOVERY_INTERNAL=1 restart_stack_after_upgrade"
        in activation
    )
    assert activation.index(commit_gate) < activation.index(helper_guard)
    assert activation.index(helper_guard) < activation.index(helper_receipt)
    postcommit = activation[activation.index(commit_gate) :]
    assert "restoring the prior checkout and runtime" not in postcommit[
        postcommit.index(helper_guard) :
    ]


def test_dev_runtime_activation_rollback_and_interruption_recovery_fail_closed() -> None:
    source = BIN_VIVENTIUM.read_text(encoding="utf-8")
    restore = source[
        source.index("restore_previous_dev_runtime_after_failure() {") :
        source.index("recover_interrupted_dev_runtime_activations() {")
    ]
    recovery = source[
        source.index("recover_interrupted_dev_runtime_activations() {") :
        source.index("dev_runtime_command() {")
    ]
    activation = source[
        source.index("dev_runtime_command() {") :
        source.index("workflows_command() {")
    ]
    prepared_rollback = extract_shell_function(
        source,
        "rollback_prepared_dev_runtime_activation",
    )
    start = source.rsplit("  start)", 1)[1].split("  launch)", 1)[0]

    assert (
        "if ! VIVENTIUM_PRESERVE_HELPER_RUNTIME_INTENT=1 \\\n"
        "    VIVENTIUM_DEV_RUNTIME_RECOVERY_INTERNAL=1 \\\n"
        "    VIVENTIUM_CLI_LOCK_INHERITED_ONCE=1 \\\n"
        "    stop_stack_for_upgrade"
        in restore
    )
    assert "refusing to replace live generated state during rollback" in restore
    assert restore.index(
        "resume_telegram_user_config_migration_if_pending"
    ) < restore.index("dev_runtime_activation_tool rollback")
    assert restore.index(
        "migrate_telegram_user_configs"
    ) < restore.index("publish_active_telegram_recovery_component")
    assert restore.index(
        "resolve_predecessor_telegram_user_config_root"
    ) < restore.index("dev_runtime_activation_tool rollback")
    assert restore.index(
        "publish_active_telegram_recovery_component"
    ) < restore.index("dev_runtime_activation_tool rollback")
    assert restore.index("clear_active_telegram_recovery_component") < (
        restore.index("remove_dev_runtime_activation_transaction")
    )
    assert "VIVENTIUM_DETACHED_LOCK_FILE=\"$previous_repo/components.lock.json\"" in (
        restore
    )
    assert "|| true" not in restore.split("dev_runtime_activation_tool rollback", 1)[0]
    assert (
        "publishing|runtime_backed_up|published|binding_applied|"
        "commit_env_accepted|commit_env_finalizing"
    ) in recovery
    assert "restore_previous_dev_runtime_after_failure" in recovery
    rolled_back_recovery = recovery.split("rolled_back)", 1)[1].split(
        "core_committed)",
        1,
    )[0]
    assert "restore_previous_dev_runtime_after_failure" in rolled_back_recovery
    assert "remove_dev_runtime_activation_transaction" not in (
        rolled_back_recovery
    )
    committed_recovery = recovery.split("core_committed)", 1)[1].split(
        "prepared)",
        1,
    )[0]
    assert "dev_runtime_owner_env_alignment_required" in committed_recovery
    assert "align_committed_dev_runtime_owner_env" in committed_recovery
    assert "runtime_checkout_refresh_helper" in committed_recovery
    assert "dev_runtime_activation_tool finalize-helper" in committed_recovery
    assert "restore_previous_dev_runtime_after_failure" not in committed_recovery
    assert committed_recovery.index(
        "dev_runtime_owner_env_alignment_required"
    ) < committed_recovery.index("runtime_checkout_refresh_helper")
    align_helper = source[
        source.index("align_committed_dev_runtime_owner_env() {") :
        source.index("remove_dev_runtime_activation_transaction() {")
    ]
    assert "currentReceipt" in align_helper
    assert "--expected-receipt-json" in align_helper
    assert (
        'VIVENTIUM_LIBRECHAT_PROMOTION_OWNER_ENV_FILE="$REPO_ROOT/'
        'viventium_v0_4/LibreChat/.env"'
    ) in align_helper
    assert (
        'VIVENTIUM_LIBRECHAT_PROMOTION_OWNER_ENV_FILE="$RUNTIME_DIR/'
        'service-env/librechat.owner.env"'
    ) not in align_helper
    assert align_helper.index("alignment-status") < align_helper.index(
        "force_restart_stack_after_owner_env_alignment"
    )
    prepared_recovery = recovery.split("prepared)", 1)[1].split(
        "publishing|runtime_backed_up",
        1,
    )[0]
    assert "restore_previous_dev_runtime_after_failure" in prepared_recovery
    assert "recover_interrupted_dev_runtime_activations" in activation
    assert "recover_interrupted_dev_runtime_activations" in start
    assert (
        "restore_dev_runtime_helper_process_after_rollback"
        in prepared_rollback
    )
    assert "restore_dev_runtime_helper_process_after_rollback" in restore
    assert (
        "VIVENTIUM_PRESERVE_HELPER_RUNTIME_INTENT=1 \\\n"
        "      VIVENTIUM_DEV_RUNTIME_RECOVERY_INTERNAL=1"
        in restore
    )
    rolled_back_recovery = recovery[
        recovery.index("      rolled_back)") :
        recovery.index("      core_committed)")
    ]
    assert "restore_previous_dev_runtime_after_failure" in (
        rolled_back_recovery
    )
    assert "remove_dev_runtime_activation_transaction" not in (
        rolled_back_recovery
    )
    stop_failure = activation[
        activation.index('if [[ "$was_running" == "1" ]]; then') :
        activation.index("if ! dev_runtime_activation_tool publish")
    ]
    assert "rollback_prepared_dev_runtime_activation" in stop_failure
    commit_boundary = activation.split(
        "LibreChat owner source or candidate revision changed at the activation commit boundary",
        1,
    )[0].rsplit('if [[ -n "$owner_env_source" ]]', 1)[1]
    assert '[[ "$owner_env_source_is_candidate" != "1" ]] &&' in commit_boundary
    assert (
        '! "$PYTHON_BIN" "$REPO_ROOT/scripts/viventium/librechat_owner_env.py" '
        "verify-source"
    ) in commit_boundary
    precommit_restart = activation.split(
        'if [[ "$restart" == "1" ]]; then',
        1,
    )[1].split('if [[ -n "$owner_env_source" ]] &&', 1)[0]
    assert "restart_stack_after_upgrade" in precommit_restart
    assert "set_helper_runtime_intent running" not in precommit_restart
    assert "VIVENTIUM_PRESERVE_HELPER_RUNTIME_INTENT=1" in precommit_restart
    assert (
        "VIVENTIUM_PRESERVE_HELPER_RUNTIME_INTENT=1"
        in restore.split("stop_stack_for_upgrade", 1)[0]
    )
    stop_failure = activation.split(
        'echo "Runtime activation could not stop the prior checkout',
        1,
    )[0].rsplit("if ! stop_stack_for_upgrade; then", 1)[1]
    assert "rollback_prepared_dev_runtime_activation" in stop_failure
    assert "set_helper_runtime_intent running" not in stop_failure
    assert "VIVENTIUM_DETACHED_REPO_ROOT=\"$previous_repo\"" in restore
    assert "VIVENTIUM_DETACHED_LOCK_FILE=\"$previous_repo/components.lock.json\"" in (
        restore
    )
    assert "load_telegram_predecessor_recovery_component" in restore
    assert "VIVENTIUM_DETACHED_COMPAT_LAUNCHER" in restore
    assert "VIVENTIUM_TELEGRAM_COMPONENT_TOOL" in restore
    assert "VIVENTIUM_TELEGRAM_POLLER_HANDOFF_HELPER" in restore
    assert '"$previous_repo/bin/viventium"' not in restore
    detached = source[
        source.index("launch_stack_detached() {") :
        source.index("detached_start_failed_early() {")
    ]
    assert 'VIVENTIUM_DETACHED_REPO_ROOT:-$REPO_ROOT' in detached
    assert 'VIVENTIUM_DETACHED_LOCK_FILE:-$LOCK_FILE' in detached


def test_dev_runtime_process_loss_reloads_exact_staged_telegram_controller() -> None:
    source = BIN_VIVENTIUM.read_text(encoding="utf-8")
    activation = source[
        source.index("dev_runtime_command() {") :
        source.index("workflows_command() {")
    ]
    recovery = extract_shell_function(
        source,
        "recover_interrupted_dev_runtime_activations",
    )

    assert (
        '--telegram-recovery-selection "$STAGED_TELEGRAM_RECOVERY_SELECTION"'
        in activation
    )
    selection_load = recovery.index("telegramRecoverySelection")
    rollback = recovery.index("restore_previous_dev_runtime_after_failure")
    assert selection_load < rollback


def test_interrupted_core_commit_retains_journal_when_finalization_fails(
    tmp_path: Path,
) -> None:
    function = extract_shell_function(
        BIN_VIVENTIUM.read_text(encoding="utf-8"),
        "recover_interrupted_dev_runtime_activations",
    )
    support = tmp_path / "support"
    transaction = support / "state" / "dev-runtime-activation.synthetic"
    transaction.mkdir(parents=True)
    remove_marker = tmp_path / "remove-called"
    completed = subprocess.run(
        [
            "bash",
            "-c",
            (
                "set -u\n"
                'APP_SUPPORT_DIR="$SUPPORT"\n'
                'PYTHON_BIN="$PYTHON_FOR_TEST"\n'
                "dev_runtime_activation_tool() {\n"
                '  if [[ "$1" == "status" ]]; then\n'
                "    printf '%s\\n' "
                '\'{"status":"core_committed","previousRepo":"/synthetic",'
                '"wasRunning":false}\'\n'
                "    return 0\n"
                "  fi\n"
                '  if [[ "$1" == "finalize-helper" ]]; then return 1; fi\n'
                "  return 0\n"
                "}\n"
                "dev_runtime_owner_env_alignment_required() { printf '0\\n'; }\n"
                "runtime_checkout_refresh_helper() { return 0; }\n"
                "is_stack_running() { return 1; }\n"
                "align_committed_dev_runtime_owner_env() { return 1; }\n"
                "restore_dev_runtime_helper_process_after_rollback() { return 0; }\n"
                "restore_previous_dev_runtime_after_failure() { return 0; }\n"
                "remove_dev_runtime_activation_transaction() {\n"
                '  printf "called\\n" >"$REMOVE_MARKER"\n'
                '  rm -rf -- "$1"\n'
                "}\n"
                f"{function}"
                "recover_interrupted_dev_runtime_activations\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={
            "HOME": str(tmp_path / "home"),
            "LANG": os.environ.get("LANG", "C"),
            "PATH": os.environ["PATH"],
            "PYTHON_FOR_TEST": sys.executable,
            "REMOVE_MARKER": str(remove_marker),
            "SUPPORT": str(support),
            "TMPDIR": str(tmp_path),
        },
    )

    assert completed.returncode != 0
    assert "helper finalization receipt is still pending" in completed.stderr
    assert transaction.is_dir()
    assert not remove_marker.exists()


def test_dev_runtime_rollback_nested_stop_inherits_recovery_and_cli_lock(
    tmp_path: Path,
) -> None:
    function = extract_shell_function(
        BIN_VIVENTIUM.read_text(encoding="utf-8"),
        "restore_previous_dev_runtime_after_failure",
    )
    capture = tmp_path / "nested stop environment"
    completed = subprocess.run(
        [
            "bash",
            "-c",
            (
                "set -euo pipefail\n"
                "stop_stack_for_upgrade() { "
                "printf 'stop:%s:%s\\n' "
                '"${VIVENTIUM_DEV_RUNTIME_RECOVERY_INTERNAL:-}" '
                '"${VIVENTIUM_CLI_LOCK_INHERITED_ONCE:-}" >"$CAPTURE_FILE"; '
                "}\n"
                    "dev_runtime_activation_tool() { printf 'rollback\\n'; }\n"
                    "load_active_telegram_recovery_component() { "
                    "TELEGRAM_PREDECESSOR_ACTIVE_CONFIG_ROOT=/tmp/synthetic-preferences; }\n"
                    "load_telegram_predecessor_recovery_component() { :; }\n"
                    "resume_telegram_user_config_migration_if_pending() { :; }\n"
                    "migrate_telegram_user_configs() { :; }\n"
                    "resolve_predecessor_telegram_user_config_root() { "
                    "printf '/tmp/synthetic-preferences\\n'; }\n"
                    "publish_active_telegram_recovery_component() { :; }\n"
                    "verify_loaded_telegram_recovery_after_rollback() { :; }\n"
                    "clear_active_telegram_recovery_component() { :; }\n"
                    "restore_dev_runtime_helper_process_after_rollback() { :; }\n"
                    "remove_dev_runtime_activation_transaction() { printf 'remove\\n'; }\n"
                f"{function}"
                "restore_previous_dev_runtime_after_failure "
                '"/tmp/synthetic-transaction" "/tmp/synthetic-previous" 0\n'
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "APP_SUPPORT_DIR": str(tmp_path / "synthetic support"),
            "CAPTURE_FILE": str(capture),
        },
    )

    assert completed.returncode == 0, completed.stderr
    assert capture.read_text(encoding="utf-8") == "stop:1:1\n"
    assert completed.stdout.splitlines() == ["remove"]


def test_dev_runtime_transaction_cannot_be_removed_while_recovery_is_active(
    tmp_path: Path,
) -> None:
    function = extract_shell_function(
        BIN_VIVENTIUM.read_text(encoding="utf-8"),
        "remove_dev_runtime_activation_transaction",
    )
    support = tmp_path / "support"
    transaction = support / "state" / "dev-runtime-activation.synthetic"
    receipt = support / "state" / "continuity" / "telegram-recovery-active.json"
    transaction.mkdir(parents=True)
    receipt.parent.mkdir(parents=True)
    receipt.write_text('{"status":"armed"}\n', encoding="utf-8")
    command = (
        "set -u\n"
        f"APP_SUPPORT_DIR={shlex.quote(str(support))}\n"
        "active_telegram_recovery_selection_file() { "
        f"printf '%s\\n' {shlex.quote(str(receipt))}; "
        "}\n"
        f"{function}"
        f"remove_dev_runtime_activation_transaction {shlex.quote(str(transaction))}\n"
    )

    blocked = subprocess.run(
        ["bash", "-c", command],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert blocked.returncode != 0
    assert "recovery is still active" in blocked.stderr
    assert transaction.is_dir()
    receipt.unlink()
    removed = subprocess.run(
        ["bash", "-c", command],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert removed.returncode == 0, removed.stderr
    assert not transaction.exists()


def test_dev_runtime_activation_never_passes_large_transaction_json_as_argv() -> None:
    source = BIN_VIVENTIUM.read_text(encoding="utf-8")
    activation_helpers = source[
        source.index("dev_runtime_owner_env_alignment_required() {") :
        source.index("dev_runtime_command() {")
    ]
    activation = source[
        source.index("dev_runtime_command() {") :
        source.index("workflows_command() {")
    ]

    assert "json.loads(sys.argv[1])" not in activation_helpers
    assert "json.loads(sys.argv[1])" not in activation
    assert activation_helpers.count("json.load(sys.stdin)") >= 5
    assert activation.count("json.load(sys.stdin)") >= 3
    assert 'printf \'%s\\n\' "$status_json" |' in activation_helpers
    assert 'printf \'%s\\n\' "$activation_begin_json" |' in activation
    assert "activation_commit_json" not in activation


def test_start_and_launch_recover_interrupted_helper_install_before_runtime() -> None:
    source = BIN_VIVENTIUM.read_text(encoding="utf-8")
    recovery = source[
        source.index("recover_interrupted_helper_install() {") :
        source.index("runtime_checkout_status() {")
    ]
    start = source.rsplit("  start)", 1)[1].split("  launch)", 1)[0]
    launch = source.rsplit("  launch)", 1)[1].split("  install-helper)", 1)[0]

    assert "helper-install-in-progress.json" in recovery
    assert "runtime_checkout_refresh_helper" in recovery
    assert "without clearing its durable recovery receipt" in recovery
    assert "recover_interrupted_helper_install" in start
    assert "recover_interrupted_helper_install" in launch


def test_runtime_entrypoints_fail_closed_through_upgrade_recovery_gate() -> None:
    cli = BIN_VIVENTIUM.read_text(encoding="utf-8")
    launcher = FULL_STACK_LAUNCHER.read_text(encoding="utf-8")
    start = cli.rsplit("  start)", 1)[1].split("  launch)", 1)[0]
    launch = cli.rsplit("  launch)", 1)[1].split("  install-helper)", 1)[0]

    assert "recover_interrupted_upgrade_before_runtime_start" in start
    assert "recover_interrupted_upgrade_before_runtime_start" in launch
    assert (
        start.index("inherit_quiesced_successor_validation_if_active")
        < start.index("recover_interrupted_upgrade_before_runtime_start")
    )
    assert (
        launch.index("inherit_quiesced_successor_validation_if_active")
        < launch.index("recover_interrupted_upgrade_before_runtime_start")
    )
    assert (
        start.index("recover_interrupted_upgrade_before_runtime_start")
        < start.index("recover_pending_quiesced_upgrade_finalization")
    )
    assert 'if [[ "${VIVENTIUM_LAUNCHER_INTERNAL:-0}" != "1" ]]' in launcher
    assert 'exec "$LAUNCHER_REPO_ROOT/bin/viventium" start "$@"' in launcher
    assert 'exec "$LAUNCHER_REPO_ROOT/bin/viventium" stop "$@"' in launcher
    assert 'VIVENTIUM_LAUNCHER_INTERNAL=1 "${START_CMD[@]}"' in cli
    assert "VIVENTIUM_LAUNCHER_INTERNAL=1 \\" in cli


@pytest.mark.parametrize(
    ("launcher_args", "expected_args"),
    [
        (("--fast",), ("start", "--fast")),
        (("--stop", "--skip-docker"), ("stop", "--skip-docker")),
    ],
)
def test_direct_full_stack_launcher_routes_through_public_cli(
    tmp_path: Path,
    launcher_args: tuple[str, ...],
    expected_args: tuple[str, ...],
) -> None:
    repo = tmp_path / "repo"
    launcher = repo / "viventium_v0_4" / "viventium-librechat-start.sh"
    cli = repo / "bin" / "viventium"
    capture = tmp_path / "cli-args.json"
    launcher.parent.mkdir(parents=True)
    cli.parent.mkdir(parents=True)
    launcher.write_bytes(FULL_STACK_LAUNCHER.read_bytes())
    launcher.chmod(0o755)
    cli.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['VIVENTIUM_QA_CAPTURE']).write_text(json.dumps(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    cli.chmod(0o755)

    environment = os.environ.copy()
    environment["VIVENTIUM_QA_CAPTURE"] = str(capture)
    environment.pop("VIVENTIUM_LAUNCHER_INTERNAL", None)
    subprocess.run(
        [str(launcher), *launcher_args],
        check=True,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert json.loads(capture.read_text(encoding="utf-8")) == list(expected_args)


def test_compile_config_preserves_compiler_failure_status() -> None:
    source = BIN_VIVENTIUM.read_text(encoding="utf-8")
    compile_block = source[source.index("compile_config() {") : source.index("sync_memory_hardening_schedule() {")]

    assert "local compile_status=0" in compile_block
    assert '"$@" || compile_status=$?' in compile_block
    assert 'if [[ "$compile_status" -ne 0 ]]; then' in compile_block
    assert 'return "$compile_status"' in compile_block


def test_dev_env_offsets_app_facing_and_runtime_sidecar_ports(tmp_path: Path) -> None:
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
    assert ports["sandpack_bundler_port"] == 4191
    assert ports["playground_port"] == 4300
    assert ports["voice_gateway_health_port"] == 9301
    assert ports["mongo_port"] == 28117
    assert ports["meili_port"] == 8700
    assert ports["livekit_http_port"] == 8888
    assert ports["livekit_tcp_port"] == 8889
    assert ports["livekit_udp_port"] == 8890
    assert ports["scheduling_mcp_port"] == 8210
    assert ports["rag_api_port"] == 8110
    assert ports["google_mcp_port"] == 8111
    assert dev_config["runtime"]["dev_env"]["shared_singleton_services"] == [
        "recall_rag",
        "searxng",
        "firecrawl",
        "google_workspace_mcp",
        "ms365_mcp",
    ]


def test_dev_env_offsets_default_sandpack_port_for_older_configs(tmp_path: Path) -> None:
    app_support = tmp_path / "App Support" / "Viventium"
    config = minimal_config()
    for key in (
        "lc_api_port",
        "lc_frontend_port",
        "sandpack_bundler_port",
        "playground_port",
        "voice_gateway_health_port",
    ):
        config["runtime"]["ports"].pop(key, None)
    config_path = app_support / "config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            str(DEV_RUNTIME),
            "--repo-root",
            str(REPO_ROOT),
            "--app-support-dir",
            str(app_support),
            "--config-file",
            str(config_path),
            "create",
            "dev",
        ],
        check=True,
    )

    dev_config = yaml.safe_load(
        (app_support / "dev-envs" / "dev" / "config.yaml").read_text(encoding="utf-8")
    )
    ports = dev_config["runtime"]["ports"]
    assert ports["lc_api_port"] == 4180
    assert ports["lc_frontend_port"] == 4190
    assert ports["sandpack_bundler_port"] == 4191
    assert ports["playground_port"] == 4300
    assert ports["voice_gateway_health_port"] == 9301
    assert ports["mongo_port"] == 28117
    assert ports["meili_port"] == 8700
    assert ports["livekit_http_port"] == 8888
    assert ports["livekit_tcp_port"] == 8889
    assert ports["livekit_udp_port"] == 8890
    assert ports["scheduling_mcp_port"] == 8210


def test_dev_env_reuses_the_canonical_validated_runtime_tools() -> None:
    dev_runtime_source = DEV_RUNTIME.read_text(encoding="utf-8")
    launcher_source = FULL_STACK_LAUNCHER.read_text(encoding="utf-8")

    assert 'env["VIVENTIUM_RUNTIME_TOOLS_DIR"] = str(' in dev_runtime_source
    assert 'Path(args.app_support_dir).expanduser().resolve() / "runtime-tools"' in dev_runtime_source
    assert 'VIVENTIUM_RUNTIME_TOOLS_DIR="${VIVENTIUM_RUNTIME_TOOLS_DIR:-' in launcher_source
    assert "${VIVENTIUM_RUNTIME_TOOLS_DIR}/node/${VIVENTIUM_NODE_RUNTIME_VERSION}" in launcher_source


def test_dev_env_run_enforces_bounded_native_thread_pools(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    cli = repo / "bin" / "viventium"
    cli.parent.mkdir(parents=True)
    capture = tmp_path / "resource-env.json"
    cli.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os\n"
        "from pathlib import Path\n"
        "keys = [\n"
        "    'OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS',\n"
        "    'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_MAX_THREADS',\n"
        "    'RAYON_NUM_THREADS', 'TOKENIZERS_PARALLELISM',\n"
        "    'VIVENTIUM_DEV_RESOURCE_GUARD', 'VIVENTIUM_DETACHED_START',\n"
        "]\n"
        "Path(os.environ['VIVENTIUM_QA_CAPTURE']).write_text(\n"
        "    json.dumps({key: os.environ.get(key) for key in keys})\n"
        ")\n",
        encoding="utf-8",
    )
    cli.chmod(0o755)

    app_support = tmp_path / "App Support" / "Viventium"
    config = app_support / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(yaml.safe_dump(minimal_config(), sort_keys=False), encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            str(DEV_RUNTIME),
            "--repo-root",
            str(repo),
            "--app-support-dir",
            str(app_support),
            "--config-file",
            str(config),
            "create",
            "dev",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    environment = os.environ.copy()
    environment["VIVENTIUM_QA_CAPTURE"] = str(capture)
    for key in (
        "OPENBLAS_NUM_THREADS",
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_MAX_THREADS",
        "RAYON_NUM_THREADS",
    ):
        environment[key] = "128"
    environment["TOKENIZERS_PARALLELISM"] = "true"
    environment["VIVENTIUM_DETACHED_START"] = "1"
    subprocess.run(
        [
            sys.executable,
            str(DEV_RUNTIME),
            "--repo-root",
            str(repo),
            "--app-support-dir",
            str(app_support),
            "--config-file",
            str(config),
            "run",
            "dev",
            "status",
        ],
        check=True,
        env=environment,
        text=True,
        capture_output=True,
    )

    assert json.loads(capture.read_text(encoding="utf-8")) == {
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "4",
        "MKL_NUM_THREADS": "1",
        "VECLIB_MAXIMUM_THREADS": "4",
        "NUMEXPR_MAX_THREADS": "4",
        "RAYON_NUM_THREADS": "4",
        "TOKENIZERS_PARALLELISM": "false",
        "VIVENTIUM_DEV_RESOURCE_GUARD": "v1",
        "VIVENTIUM_DETACHED_START": "0",
    }


def test_macos_resource_guard_counts_reparented_candidate_python_with_spaced_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = importlib.util.spec_from_file_location("viventium_dev_runtime_guard", DEV_RUNTIME)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    thread_inspections: list[int] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if command == ["/bin/ps", "-axo", "pid=,ppid=,pgid=,comm="]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    "4000 1 4000 bash\n"
                    "4321 1 4000 /Applications/Synthetic Runtime/Python\n"
                    "5000 4321 4000 child\n"
                    "9000 1 9000 /opt/homebrew/bin/python3\n"
                ),
                stderr="",
            )
        assert command[:3] == ["/bin/ps", "-M", "-p"]
        inspected_pid = int(command[3])
        thread_inspections.append(inspected_pid)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="HEADER\nthread-one\nthread-two\nthread-three\n",
            stderr="",
        )

    monkeypatch.setattr(module.sys, "platform", "darwin")
    monkeypatch.setattr(module.subprocess, "run", fake_run)

    snapshot = module.process_thread_snapshot(4000)

    assert snapshot[4321] == (1, 3)
    assert thread_inspections == [4321]


def test_macos_resource_guard_fails_closed_when_live_python_threads_cannot_be_inspected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = importlib.util.spec_from_file_location("viventium_dev_runtime_guard_failure", DEV_RUNTIME)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if command == ["/bin/ps", "-axo", "pid=,ppid=,pgid=,comm="]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="4321 1 4000 /Applications/Synthetic Runtime/Python\n",
                stderr="",
            )
        raise subprocess.TimeoutExpired(command, timeout=2)

    monkeypatch.setattr(module.sys, "platform", "darwin")
    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module.os, "kill", lambda _pid, _signal: None)

    assert module.process_thread_snapshot(4000) is None


def test_dev_env_run_stops_a_python_process_before_thread_budget_exhaustion(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    cli = repo / "bin" / "viventium"
    cli.parent.mkdir(parents=True)
    cli.write_text(
        "#!/usr/bin/env python3\n"
        "import threading, time\n"
        "stop = threading.Event()\n"
        "for _ in range(8):\n"
        "    threading.Thread(target=stop.wait, daemon=True).start()\n"
        "print('synthetic runaway ready', flush=True)\n"
        "while True:\n"
        "    time.sleep(1)\n",
        encoding="utf-8",
    )
    cli.chmod(0o755)

    app_support = tmp_path / "App Support" / "Viventium"
    config = app_support / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(yaml.safe_dump(minimal_config(), sort_keys=False), encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            str(DEV_RUNTIME),
            "--repo-root",
            str(repo),
            "--app-support-dir",
            str(app_support),
            "--config-file",
            str(config),
            "create",
            "dev",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    environment = os.environ.copy()
    environment["VIVENTIUM_DEV_RESOURCE_GUARD_MAX_PROCESS_THREADS"] = "4"
    completed = subprocess.run(
        [
            sys.executable,
            str(DEV_RUNTIME),
            "--repo-root",
            str(repo),
            "--app-support-dir",
            str(app_support),
            "--config-file",
            str(config),
            "run",
            "dev",
            "status",
        ],
        env=environment,
        text=True,
        capture_output=True,
        timeout=8,
        check=False,
    )

    assert completed.returncode == 86
    assert "resource guard stopped the dev env" in completed.stderr.lower()
    assert "thread budget" in completed.stderr.lower()


def test_dev_env_run_enforces_the_candidate_python_tree_budget(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    cli = repo / "bin" / "viventium"
    cli.parent.mkdir(parents=True)
    cli.write_text(
        "#!/usr/bin/env python3\n"
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([\n"
        "    sys.executable, '-c',\n"
        "    \"import threading,time; "
        "[threading.Thread(target=lambda: time.sleep(30), daemon=True).start() "
        "for _ in range(3)]; print('child ready', flush=True); time.sleep(30)\",\n"
        "])\n"
        "print('tree ready', flush=True)\n"
        "child.wait()\n",
        encoding="utf-8",
    )
    cli.chmod(0o755)

    app_support = tmp_path / "App Support" / "Viventium"
    config = app_support / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(yaml.safe_dump(minimal_config(), sort_keys=False), encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            str(DEV_RUNTIME),
            "--repo-root",
            str(repo),
            "--app-support-dir",
            str(app_support),
            "--config-file",
            str(config),
            "create",
            "dev",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    environment = os.environ.copy()
    environment["VIVENTIUM_DEV_RESOURCE_GUARD_MAX_PROCESS_THREADS"] = "4"
    environment["VIVENTIUM_DEV_RESOURCE_GUARD_MAX_TREE_THREADS"] = "4"
    completed = subprocess.run(
        [
            sys.executable,
            str(DEV_RUNTIME),
            "--repo-root",
            str(repo),
            "--app-support-dir",
            str(app_support),
            "--config-file",
            str(config),
            "run",
            "dev",
            "status",
        ],
        env=environment,
        text=True,
        capture_output=True,
        timeout=8,
        check=False,
    )

    assert completed.returncode == 86
    assert "process tree reached" in completed.stderr.lower()


@pytest.mark.parametrize(
    ("guard_signal", "expected_status"),
    ((signal.SIGINT, 130), (signal.SIGTERM, 128 + signal.SIGTERM)),
)
def test_dev_env_run_forwards_operator_signals_and_waits_for_child_cleanup(
    tmp_path: Path,
    guard_signal: signal.Signals,
    expected_status: int,
) -> None:
    repo = tmp_path / "repo"
    cli = repo / "bin" / "viventium"
    cli.parent.mkdir(parents=True)
    cleanup_marker = tmp_path / "cleanup-complete"
    child_pid_file = tmp_path / "child.pid"
    cli.write_text(
        "#!/usr/bin/env python3\n"
        "import os, signal, time\n"
        "from pathlib import Path\n"
        "marker = Path(os.environ['VIVENTIUM_QA_CLEANUP_MARKER'])\n"
        "Path(os.environ['VIVENTIUM_QA_CHILD_PID']).write_text(str(os.getpid()))\n"
        "def cleanup(_signum, _frame):\n"
        "    time.sleep(0.3)\n"
        "    marker.write_text('drained')\n"
        "    raise SystemExit(0)\n"
        "signal.signal(signal.SIGINT, cleanup)\n"
        "signal.signal(signal.SIGTERM, cleanup)\n"
        "print('cleanup child ready', flush=True)\n"
        "while True:\n"
        "    time.sleep(1)\n",
        encoding="utf-8",
    )
    cli.chmod(0o755)

    app_support = tmp_path / "App Support" / "Viventium"
    config = app_support / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(yaml.safe_dump(minimal_config(), sort_keys=False), encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            str(DEV_RUNTIME),
            "--repo-root",
            str(repo),
            "--app-support-dir",
            str(app_support),
            "--config-file",
            str(config),
            "create",
            "dev",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    environment = os.environ.copy()
    environment["VIVENTIUM_QA_CLEANUP_MARKER"] = str(cleanup_marker)
    environment["VIVENTIUM_QA_CHILD_PID"] = str(child_pid_file)
    guard = subprocess.Popen(
        [
            sys.executable,
            str(DEV_RUNTIME),
            "--repo-root",
            str(repo),
            "--app-support-dir",
            str(app_support),
            "--config-file",
            str(config),
            "run",
            "dev",
            "status",
        ],
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert guard.stdout is not None
        assert guard.stdout.readline().strip() == "cleanup child ready"
        guard.send_signal(guard_signal)
        assert guard.wait(timeout=5) == expected_status
        assert cleanup_marker.read_text(encoding="utf-8") == "drained"
    finally:
        if guard.poll() is None:
            guard.kill()
            guard.wait(timeout=2)
        if child_pid_file.exists():
            child_pid = int(child_pid_file.read_text(encoding="utf-8"))
            try:
                os.killpg(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_dev_env_shared_singletons_compile_without_duplicate_start_flags(tmp_path: Path) -> None:
    config = minimal_config()
    config["runtime"]["dev_env"] = {
        "enabled": True,
        "name": "dev",
        "port_offset": 1000,
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
    assert "VIVENTIUM_SCHEDULING_MCP_PORT=8210" in env_text
    assert "SCHEDULING_MCP_URL=http://localhost:8210/mcp" in env_text
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
        check=False,
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
        check=False,
        text=True,
        stdout=subprocess.PIPE,
    )
    payload = json.loads(proc.stdout)
    assert proc.returncode == 3
    assert payload["helper_needs_rebuild"] is True
    assert "helper_rebuild_needed" in payload["blockers"]


def test_upgrade_check_blocks_untracked_parent_work_before_any_mutation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "components.lock.json").write_text('{"components": []}\n', encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "add", "components.lock.json"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "parent"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
    )
    (repo / "untracked-user-work.txt").write_text("preserve me\n", encoding="utf-8")
    app_support = tmp_path / "absent-app-support"

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
        check=False,
        text=True,
        stdout=subprocess.PIPE,
    )
    payload = json.loads(proc.stdout)

    assert proc.returncode == 3
    assert payload["dirty_checkout"] is True
    assert "dirty_checkout" in payload["blockers"]
    assert not app_support.exists()


def test_upgrade_check_ignores_directory_named_like_stack_pid_marker(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("viventium_upgrade_check_stack_marker", UPGRADE_CHECK)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    app_support = tmp_path / "app-support"
    (app_support / "state" / "runtime" / "isolated" / "detached-launch.pgid").mkdir(parents=True)

    assert module.stack_running(app_support) is False


def test_upgrade_check_refuses_to_assume_origin_when_branch_has_no_configured_remote(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    (repo / "tracked.txt").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "fixture"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
    )
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True)
    subprocess.run(["git", "push", "origin", "HEAD:refs/heads/master"], cwd=repo, check=True, stdout=subprocess.PIPE)
    spec = importlib.util.spec_from_file_location("viventium_upgrade_check_remote", UPGRADE_CHECK)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    branch = module.current_branch(repo)

    result = module.observe_remote(repo, branch)

    assert result["error"] == "remote_unavailable"
    assert result["upstream"] == "<configured-upstream>"


def test_upgrade_check_fails_closed_on_dirty_pinned_component(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    component = repo / "component"
    component.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=component, check=True, stdout=subprocess.PIPE)
    tracked = component / "tracked.txt"
    tracked.write_text("pinned\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=component, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "pinned"],
        cwd=component,
        check=True,
        stdout=subprocess.PIPE,
    )
    pinned_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=component,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    subprocess.run(
        ["git", "remote", "add", "origin", "git@github.com:ProjectViventium/test-component.git"],
        cwd=component,
        check=True,
    )
    (repo / "components.lock.json").write_text(
        json.dumps(
            {
                "components": [
                    {
                        "name": "LibreChat",
                        "origin": "https://github.com/ProjectViventium/test-component.git",
                        "path": "component",
                        "ref": pinned_commit,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "add", "components.lock.json"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "parent"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
    )
    tracked.write_text("local edit\n", encoding="utf-8")
    (component / "local-note.txt").write_text("untracked local work\n", encoding="utf-8")
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
        check=False,
        text=True,
        stdout=subprocess.PIPE,
    )

    payload = json.loads(proc.stdout)
    assert proc.returncode == 3
    assert payload["ready_to_upgrade"] is False
    assert "component_lock_drift" in payload["blockers"]
    assert payload["component_lock_drift"] == [
        {
            "actual": pinned_commit,
            "expected": pinned_commit,
            "name": "LibreChat",
            "path": "component",
            "status": "dirty_worktree",
        }
    ]


def test_upgrade_check_reports_clean_component_head_mismatch_as_refreshable(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    component = repo / "component"
    component.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=component, check=True, stdout=subprocess.PIPE)
    tracked = component / "tracked.txt"
    tracked.write_text("pinned\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=component, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "pinned"],
        cwd=component,
        check=True,
        stdout=subprocess.PIPE,
    )
    pinned_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=component,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    tracked.write_text("new commit\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=component, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "ahead"],
        cwd=component,
        check=True,
        stdout=subprocess.PIPE,
    )
    actual_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=component,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    subprocess.run(
        ["git", "remote", "add", "origin", "git@github.com:ProjectViventium/test-component.git"],
        cwd=component,
        check=True,
    )
    (repo / "components.lock.json").write_text(
        json.dumps(
            {
                "components": [
                    {
                        "name": "LibreChat",
                        "origin": "https://github.com/ProjectViventium/test-component.git",
                        "path": "component",
                        "ref": pinned_commit,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "add", "components.lock.json"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "parent"],
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
        check=False,
        text=True,
        stdout=subprocess.PIPE,
    )

    payload = json.loads(proc.stdout)
    assert proc.returncode == 0
    assert payload["ready_to_upgrade"] is True
    assert payload["update_available"] is True
    assert payload["component_lock_drift"] == []
    assert payload["component_refresh_required"] == [
        {
            "actual": actual_commit,
            "expected": pinned_commit,
            "name": "LibreChat",
            "path": "component",
            "status": "head_mismatch",
        }
    ]


def test_upgrade_check_blocks_unrelated_component_origin_instead_of_refreshing(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    component = repo / "component"
    component.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=component, check=True, stdout=subprocess.PIPE)
    (component / "tracked.txt").write_text("local checkout\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=component, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "local"],
        cwd=component,
        check=True,
        stdout=subprocess.PIPE,
    )
    actual_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=component,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    unrelated_origin = tmp_path / "unrelated.git"
    subprocess.run(["git", "init", "--bare", str(unrelated_origin)], check=True, stdout=subprocess.PIPE)
    subprocess.run(
        ["git", "remote", "add", "origin", str(unrelated_origin)],
        cwd=component,
        check=True,
    )
    expected_origin = tmp_path / "expected.git"
    subprocess.run(["git", "init", "--bare", str(expected_origin)], check=True, stdout=subprocess.PIPE)
    expected_commit = "1" * 40
    (repo / "components.lock.json").write_text(
        json.dumps(
            {
                "components": [
                    {
                        "name": "LibreChat",
                        "origin": str(expected_origin),
                        "path": "component",
                        "ref": expected_commit,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    spec = importlib.util.spec_from_file_location(
        "viventium_upgrade_check_unrelated_component_origin",
        UPGRADE_CHECK,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    blockers, refresh_required = module.component_alignment(repo)

    assert refresh_required == []
    assert blockers == [
        {
            "actual": actual_commit,
            "expected": expected_commit,
            "name": "LibreChat",
            "path": "component",
            "status": "origin_mismatch",
        }
    ]


def test_upgrade_check_clean_alignment_exits_successfully(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    (repo / "components.lock.json").write_text('{"components": []}\n', encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "clean"],
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
        check=False,
        text=True,
        stdout=subprocess.PIPE,
    )

    payload = json.loads(proc.stdout)
    assert proc.returncode == 0
    assert payload["ready_to_upgrade"] is True
    assert payload["blockers"] == []


def test_upgrade_check_observes_remote_without_mutating_git_metadata(tmp_path: Path) -> None:
    origin = tmp_path / "origin.git"
    seed = tmp_path / "seed"
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "--bare", str(origin)], check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "clone", str(origin), str(seed)], check=True, stdout=subprocess.PIPE)
    (seed / "components.lock.json").write_text('{"components": []}\n', encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=seed, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "initial"],
        cwd=seed,
        check=True,
        stdout=subprocess.PIPE,
    )
    subprocess.run(["git", "push", "-u", "origin", "HEAD"], cwd=seed, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "clone", str(origin), str(repo)], check=True, stdout=subprocess.PIPE)
    (seed / "remote-change.txt").write_text("new release\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=seed, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "remote update"],
        cwd=seed,
        check=True,
        stdout=subprocess.PIPE,
    )
    subprocess.run(["git", "push"], cwd=seed, check=True, stdout=subprocess.PIPE)
    fetch_head = repo / ".git" / "FETCH_HEAD"
    fetch_head_before = fetch_head.read_bytes() if fetch_head.exists() else None
    app_support = tmp_path / "does-not-exist" / "Viventium"

    proc = subprocess.run(
        [
            sys.executable,
            str(UPGRADE_CHECK),
            "--repo-root",
            str(repo),
            "--app-support-dir",
            str(app_support),
            "--json",
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
    )

    payload = json.loads(proc.stdout)
    assert proc.returncode == 0
    assert payload["update_available"] is True
    assert payload["remote_history_complete"] is False
    assert (fetch_head.read_bytes() if fetch_head.exists() else None) == fetch_head_before
    assert not app_support.exists()


def test_upgrade_check_does_not_block_on_unselected_dirty_component(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    component = repo / "glasshive"
    component.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=component, check=True, stdout=subprocess.PIPE)
    tracked = component / "tracked.txt"
    tracked.write_text("pinned\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=component, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "pinned"],
        cwd=component,
        check=True,
        stdout=subprocess.PIPE,
    )
    pinned_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=component,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    tracked.write_text("private local work\n", encoding="utf-8")
    (repo / "components.lock.json").write_text(
        json.dumps(
            {
                "components": [
                    {
                        "name": "LibreChat",
                        "origin": "https://github.com/ProjectViventium/viventium-librechat.git",
                        "path": "librechat",
                        "ref": "1" * 40,
                    },
                    {
                        "name": "GlassHive",
                        "path": "glasshive",
                        "ref": pinned_commit,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    config = repo / "config.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "voice": {"mode": "disabled"},
                "runtime": {"playground_variant": "modern"},
                "integrations": {"glasshive": {"enabled": False}},
            }
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "add", "components.lock.json", "config.yaml"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "parent"],
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
            "--config-file",
            str(config),
            "--no-fetch",
            "--json",
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
    )

    payload = json.loads(proc.stdout)
    assert proc.returncode == 0
    assert payload["component_lock_drift"] == []
    assert [item["name"] for item in payload["component_refresh_required"]] == ["LibreChat"]

    stock_python_proc = subprocess.run(
        [
            sys.executable,
            "-S",
            str(UPGRADE_CHECK),
            "--repo-root",
            str(repo),
            "--app-support-dir",
            str(app_support),
            "--config-file",
            str(config),
            "--no-fetch",
            "--json",
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
    )

    stock_python_payload = json.loads(stock_python_proc.stdout)
    assert stock_python_proc.returncode == 0
    assert stock_python_payload["component_lock_drift"] == []
    assert [item["name"] for item in stock_python_payload["component_refresh_required"]] == [
        "LibreChat"
    ]


def test_upgrade_check_component_selection_parser_handles_canonical_yaml_without_pyyaml(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        """
voice:
  mode: 'O''Brien #1'
runtime:
  playground_variant: "modern#stable" # real comment
integrations:
  glasshive:
    enabled: false
  google_workspace:
    enabled: true
  ms365:
    enabled: false
  openclaw:
    enabled: false
  skyvern:
    enabled: false
unrelated:
  owner_note: 'O''Brien # private syntax exercise'
""".lstrip(),
        encoding="utf-8",
    )
    spec = importlib.util.spec_from_file_location(
        "viventium_upgrade_check_selection_parser",
        UPGRADE_CHECK,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.load_component_selection_config(config) == {
        "voice": {"mode": "O'Brien #1"},
        "runtime": {"playground_variant": "modern#stable"},
        "integrations": {
            "glasshive": {"enabled": False},
            "google_workspace": {"enabled": True},
            "ms365": {"enabled": False},
            "openclaw": {"enabled": False},
            "skyvern": {"enabled": False},
        },
    }


@pytest.mark.parametrize(
    "body",
    [
        "integrations:\n  glasshive:\n    enabled: false\n    enabled: true\n",
        "integrations:\n  glasshive:\n    enabled: [false]\n",
        "runtime:\n\tplayground_variant: modern\n",
        "voice:\n  mode: 'unterminated\n",
    ],
)
def test_upgrade_check_component_selection_parser_fails_closed(
    tmp_path: Path,
    body: str,
) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(body, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(
        "viventium_upgrade_check_selection_parser_invalid",
        UPGRADE_CHECK,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    with pytest.raises(ValueError):
        module.load_component_selection_config(config)


def test_helper_preserves_blocker_details_from_nonzero_upgrade_check() -> None:
    source = HELPER_SOURCE.read_text(encoding="utf-8")
    check_section = source[source.index("    func checkForUpdates() {") : source.index("    func startHealWorkflow() {")]

    assert "summary.statusReadable" in check_section
    assert "result.exitStatus != 0 && !summary.statusReadable" in check_section
    assert 'blockers.contains("fetch_failed")' in source


def test_upgrade_check_rejects_unsafe_component_paths_and_redacts_local_details(tmp_path: Path) -> None:
    repo = tmp_path / "private-repo-name"
    repo.mkdir()
    (repo / "components.lock.json").write_text(
        json.dumps(
            {
                "components": [
                    {
                        "name": "LibreChat",
                        "path": "../outside",
                        "ref": "1" * 40,
                    },
                    {
                        "name": "agent-starter-react",
                        "path": "missing",
                        "ref": "main",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "fixture"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
    )
    branch = subprocess.run(
        ["git", "branch", "--show-current"], cwd=repo, check=True, text=True, stdout=subprocess.PIPE
    ).stdout.strip()
    subprocess.run(["git", "config", f"branch.{branch}.remote", "missing-secret-remote"], cwd=repo, check=True)

    proc = subprocess.run(
        [
            sys.executable,
            str(UPGRADE_CHECK),
            "--repo-root",
            str(repo),
            "--app-support-dir",
            str(tmp_path / "absent"),
            "--json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    payload = json.loads(proc.stdout)
    assert proc.returncode == 2
    assert payload["schema_version"] == 1
    assert payload["repo_root"] == "<repo>"
    assert payload["fetch_error"] == "remote_unavailable"
    assert str(tmp_path) not in proc.stdout
    assert "missing-secret-remote" not in proc.stdout
    assert "../outside" not in proc.stdout
    statuses = {item["status"] for item in payload["component_lock_drift"]}
    assert {"unsafe_path", "invalid_ref"}.issubset(statuses)


def test_upgrade_check_requires_prebuilt_binary_and_digest_for_helper_alignment(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    helper = repo / "apps" / "macos" / "ViventiumHelper"
    (helper / "Sources" / "ViventiumHelper" / "Resources").mkdir(parents=True)
    (helper / "prebuilt").mkdir(parents=True)
    (helper / "Package.swift").write_text("package\n", encoding="utf-8")
    (helper / "Sources" / "ViventiumHelper" / "ViventiumHelperApp.swift").write_text("source\n", encoding="utf-8")
    (helper / "Sources" / "ViventiumHelper" / "Resources" / "Info.plist").write_text("plist\n", encoding="utf-8")
    digest = hashlib.sha256()
    for relative in (
        Path("Package.swift"),
        Path("Sources/ViventiumHelper/ViventiumHelperApp.swift"),
        Path("Sources/ViventiumHelper/Resources/Info.plist"),
    ):
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update((helper / relative).read_bytes())
        digest.update(b"\0")
    (helper / "prebuilt" / "source.sha256").write_text(digest.hexdigest() + "\n", encoding="utf-8")

    spec = importlib.util.spec_from_file_location("viventium_upgrade_check", UPGRADE_CHECK)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.helper_needs_rebuild(repo) is True


def test_upgrade_check_git_timeout_returns_only_a_generic_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = importlib.util.spec_from_file_location("viventium_upgrade_check_timeout", UPGRADE_CHECK)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def raise_timeout(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd=["git", "private-remote"], timeout=15)

    monkeypatch.setattr(module.subprocess, "run", raise_timeout)
    result = module.run_git(tmp_path, "status")
    assert result.returncode == 124
    assert result.stdout == ""
    assert result.stderr == "git_command_failed"
    assert "private-remote" not in result.stderr


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
    assert '"playground": ("http://localhost:3300/api/health", {200})' in source
    assert "http://127.0.0.1:3180" not in source
    assert "http://127.0.0.1:3190" not in source
    assert "http://127.0.0.1:3300" not in source


def test_cli_optional_telegram_surface_requires_api_health() -> None:
    source = BIN_VIVENTIUM.read_text(encoding="utf-8")
    assert "telegram_bridge_surface_healthy() {" in source
    assert "scripts/viventium/telegram_poller_handoff.py\" health" in source
    assert "--require-receipt" in source
    assert 'runtime_pid_file_running "telegram_bot.pid"' not in source
    assert 'runtime_pid_file_running "telegram_bot_deferred.pid"' not in source
    assert 'api_surface_healthy "$api_port"' in source


def test_install_summary_uses_lightweight_playground_health_probe() -> None:
    source = INSTALL_SUMMARY.read_text(encoding="utf-8")
    assert "def url_with_path(url: str, path: str) -> str:" in source
    assert 'url_with_path(playground_url, "/api/health")' in source
    assert 'f"http://127.0.0.1:{playground_port}/api/health"' in source
    assert 'f"http://127.0.0.1:{playground_port}",' not in source


def test_modern_playground_exposes_lightweight_health_route() -> None:
    health_route = REPO_ROOT / "viventium_v0_4" / "agent-starter-react" / "app" / "api" / "health" / "route.ts"
    content = health_route.read_text(encoding="utf-8")
    assert "VIVENTIUM START" in content
    assert "NextResponse.json" in content
    assert "surface: 'modern-playground'" in content
    assert "'Cache-Control': 'no-store'" in content


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
        "Text(self.controller.statusLabel)",
        'Menu("Advanced")',
    ]:
        assert top_level_label in menu_body

    # Status is informational, so it must not masquerade as a disabled button to
    # keyboard or assistive-technology users.
    assert "Button(self.controller.statusLabel)" not in menu_body

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
