#!/usr/bin/env python3
"""Local operator wrapper for Viventium saved-memory hardening."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import power_budget


DEFAULT_SCHEDULE = "0 3 * * *"
DEFAULT_TIMEZONE = "America/Toronto"
LAUNCH_AGENT_LABEL = "ai.viventium.memory-harden"
PARTIAL_BACKFILL_EXIT = 2
TRIGGER_EVENT_SCHEMA_VERSION = 1


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def runtime_env_candidates(runtime_dir: Path, librechat_dir: Path) -> tuple[Path, ...]:
    """Return env files from lowest to highest precedence."""
    return (
        librechat_dir / ".env",
        runtime_dir / "local.env",
        runtime_dir / "librechat.env",
        runtime_dir / "runtime.env",
        runtime_dir / "runtime.local.env",
        runtime_dir / "service-env" / "librechat.env",
    )


def load_runtime_env(runtime_dir: Path, librechat_dir: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for candidate in runtime_env_candidates(runtime_dir, librechat_dir):
        for key, value in parse_env_file(candidate).items():
            if value == "" and env.get(key):
                continue
            env[key] = value
    return env


def cron_to_launchd_time(schedule: str) -> tuple[int, int]:
    parts = schedule.split()
    if len(parts) != 5:
        raise SystemExit("memory hardening LaunchAgent currently expects a 5-field cron schedule")
    minute, hour, day, month, weekday = parts
    if day != "*" or month != "*" or weekday != "*":
        raise SystemExit("memory hardening LaunchAgent currently supports daily schedules only")
    try:
        hour_i = int(hour)
        minute_i = int(minute)
    except ValueError as exc:
        raise SystemExit(f"Invalid daily schedule: {schedule}") from exc
    if not 0 <= hour_i <= 23 or not 0 <= minute_i <= 59:
        raise SystemExit(f"Invalid daily schedule: {schedule}")
    return hour_i, minute_i


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def local_timezone_name() -> str:
    tz = os.environ.get("TZ", "").strip()
    if tz:
        return tz
    try:
        localtime = os.path.realpath("/etc/localtime")
        marker = "/zoneinfo/"
        if marker in localtime:
            return localtime.split(marker, 1)[1]
    except OSError:
        pass
    return time.tzname[time.localtime().tm_isdst > 0] or "local"


def public_hash(value: object, length: int = 16) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:length]


def trigger_events_dir(app_support_dir: Path) -> Path:
    return app_support_dir / "state" / "memory-hardening" / "schedule-events"


def trigger_source_for_args(args: argparse.Namespace) -> str:
    explicit = str(getattr(args, "trigger", "") or "").strip().lower()
    if explicit:
        return explicit
    if getattr(args, "scheduled", False):
        return "scheduled_legacy"
    return ""


def trigger_schedule_payload(env: dict[str, str]) -> dict[str, object]:
    schedule = env.get("VIVENTIUM_MEMORY_HARDENING_SCHEDULE") or DEFAULT_SCHEDULE
    payload: dict[str, object] = {
        "kind": "StartCalendarInterval",
        "cron": schedule,
        "timezone_context": env.get("VIVENTIUM_MEMORY_HARDENING_TIMEZONE") or DEFAULT_TIMEZONE,
    }
    try:
        hour, minute = cron_to_launchd_time(schedule)
    except SystemExit:
        payload["valid"] = False
    else:
        payload.update({"valid": True, "hour": hour, "minute": minute})
    return payload


def find_latest_run_summary_after(app_support_dir: Path, started_at: datetime) -> dict[str, object] | None:
    runs_dir = app_support_dir / "state" / "memory-hardening" / "runs"
    if not runs_dir.is_dir():
        return None
    candidates: list[tuple[float, dict[str, object]]] = []
    cutoff = started_at.timestamp() - 60
    for summary_path in runs_dir.glob("*/summary.json"):
        try:
            stat = summary_path.stat()
        except OSError:
            continue
        if stat.st_mtime < cutoff:
            continue
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(summary, dict):
            candidates.append((stat.st_mtime, summary))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def write_json_private(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def start_trigger_event(args: argparse.Namespace, env: dict[str, str]) -> tuple[Path, datetime] | None:
    trigger_source = trigger_source_for_args(args)
    if not trigger_source:
        return None
    fired_at = utc_now()
    local_fired_at = fired_at.astimezone()
    event_id = f"{trigger_source}-{fired_at.strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}"
    payload: dict[str, object] = {
        "schemaVersion": TRIGGER_EVENT_SCHEMA_VERSION,
        "event_id": event_id,
        "status": "started",
        "trigger_source": trigger_source,
        "scheduled_invocation": bool(getattr(args, "scheduled", False)),
        "schedule_label": LAUNCH_AGENT_LABEL if trigger_source == "launchd" else "",
        "schedule": trigger_schedule_payload(env),
        "fired_at_utc": iso_z(fired_at),
        "fired_at_local": local_fired_at.isoformat(timespec="milliseconds"),
        "timezone_at_fire": local_timezone_name(),
        "command": str(getattr(args, "command", "") or ""),
        "pid": os.getpid(),
        "repo_root_hash": public_hash(getattr(args, "repo_root", "")),
        "runtime_dir_hash": public_hash(getattr(args, "runtime_dir", "")),
    }
    path = trigger_events_dir(args.app_support_dir) / f"{event_id}.json"
    write_json_private(path, payload)
    return path, fired_at


def finish_trigger_event(
    event: tuple[Path, datetime] | None,
    args: argparse.Namespace,
    exit_code: int,
    *,
    status: str | None = None,
    reason: str | None = None,
) -> int:
    if event is None:
        return exit_code
    path, started_at = event
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    finished_at = utc_now()
    final_status = status or ("success" if exit_code == 0 else "failed")
    payload.update(
        {
            "status": final_status,
            "exit_code": exit_code,
            "finished_at_utc": iso_z(finished_at),
            "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
            "executed_command": str(getattr(args, "command", "") or ""),
        }
    )
    if reason:
        payload["reason"] = reason
    latest_summary = find_latest_run_summary_after(args.app_support_dir, started_at)
    if latest_summary:
        payload["run_id"] = latest_summary.get("run_id")
        payload["run_status"] = latest_summary.get("status")
    write_json_private(path, payload)
    return exit_code


def launch_agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def install_schedule(args: argparse.Namespace, runtime_env: dict[str, str]) -> dict[str, object]:
    if sys.platform != "darwin":
        raise SystemExit("install-schedule currently supports macOS LaunchAgents. Use cron/systemd on Linux.")
    schedule = args.schedule or runtime_env.get("VIVENTIUM_MEMORY_HARDENING_SCHEDULE") or DEFAULT_SCHEDULE
    hour, minute = cron_to_launchd_time(schedule)
    plist_path = launch_agent_path()
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    logs_dir = args.app_support_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    launch_path = ":".join(
        [
            str(Path.home() / ".local" / "bin"),
            str(Path.home() / ".codex" / "bin"),
            "/Applications/Codex.app/Contents/Resources",
            "/opt/homebrew/bin",
            "/opt/homebrew/sbin",
            "/usr/local/bin",
            "/usr/bin",
            "/bin",
            "/usr/sbin",
            "/sbin",
        ]
    )
    program_arguments = [
        "/usr/bin/env",
        "-i",
        f"HOME={str(Path.home())}",
        f"USER={os.environ.get('USER', '')}",
        f"LOGNAME={os.environ.get('LOGNAME', os.environ.get('USER', ''))}",
        "SHELL=/bin/zsh",
        f"PATH={launch_path}",
        "LANG=en_US.UTF-8",
        "LC_ALL=en_US.UTF-8",
        "python3",
        str(args.repo_root / "scripts" / "viventium" / "memory_harden.py"),
        "--repo-root",
        str(args.repo_root),
        "--app-support-dir",
        str(args.app_support_dir),
        "--runtime-dir",
        str(args.runtime_dir),
        "apply",
        "--scheduled",
        "--trigger",
        "launchd",
    ]
    operator_user_email = args.user_email or runtime_env.get("VIVENTIUM_MEMORY_HARDENING_USER_EMAIL")
    if operator_user_email:
        program_arguments.extend(["--user-email", operator_user_email])
    payload = {
        "Label": LAUNCH_AGENT_LABEL,
        "ProgramArguments": program_arguments,
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "StandardOutPath": str(logs_dir / "memory-hardening.log"),
        "StandardErrorPath": str(logs_dir / "memory-hardening.err.log"),
        "WorkingDirectory": str(args.app_support_dir),
        "RunAtLoad": False,
    }
    with plist_path.open("wb") as handle:
        plistlib.dump(payload, handle)
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(plist_path)], check=False)
    bootstrap = subprocess.run(
        ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if bootstrap.returncode != 0:
        detail = (bootstrap.stderr or bootstrap.stdout or "").strip()
        raise SystemExit(
            "failed to install memory hardening LaunchAgent"
            + (f": {detail}" if detail else "")
        )
    return {"installed": True, "label": LAUNCH_AGENT_LABEL, "schedule": schedule, "plist": str(plist_path)}


def uninstall_schedule(args: argparse.Namespace) -> dict[str, object]:
    plist_path = launch_agent_path()
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(plist_path)], check=False)
    if plist_path.exists():
        plist_path.unlink()
    marker = args.app_support_dir / "state" / "memory-hardening" / "dry-run-first-complete"
    if marker.exists():
        marker.unlink()
    return {"installed": False, "label": LAUNCH_AGENT_LABEL, "plist": str(plist_path)}


def model_for_provider(provider: str | None, runtime_env: dict[str, str]) -> str:
    normalized = str(provider or "").strip().lower().replace("-", "_")
    if normalized in {"anthropic", "claude", "claude_code"}:
        return runtime_env.get("VIVENTIUM_MEMORY_HARDENING_ANTHROPIC_MODEL", "")
    if normalized in {"openai", "openai_api", "codex"}:
        return runtime_env.get("VIVENTIUM_MEMORY_HARDENING_OPENAI_MODEL", "")
    return ""


def user_email_for_run(args: argparse.Namespace, runtime_env: dict[str, str]) -> str:
    if getattr(args, "user_id", None):
        return str(getattr(args, "user_email", "") or "")
    return str(
        getattr(args, "user_email", "")
        or runtime_env.get("VIVENTIUM_MEMORY_HARDENING_USER_EMAIL")
        or ""
    ).strip()


def bool_env_disabled(value: str | None) -> bool:
    return power_budget.bool_env_disabled(value)


def command_uses_model_work(args: argparse.Namespace) -> bool:
    return str(getattr(args, "command", "") or "") in {"dry-run", "apply", "ingest-transcripts"}


def running_on_battery_power() -> bool:
    return power_budget.running_on_battery_power()


def thermal_state_constrained() -> bool:
    return power_budget.thermal_state_constrained()


def power_gate_skip_reason(args: argparse.Namespace, env: dict[str, str]) -> str | None:
    if not command_uses_model_work(args):
        return None
    return power_budget.skip_reason(
        env=env,
        gate_env_name="VIVENTIUM_MEMORY_HARDENING_POWER_GATE",
        ignore_power_gate=getattr(args, "ignore_power_gate", False),
        override_env_name="VIVENTIUM_MEMORY_HARDENING_ALLOW_POWER_OVERRIDE",
        running_on_battery=running_on_battery_power(),
        thermal_constrained=thermal_state_constrained(),
    )


def emit_resource_gate_skip(args: argparse.Namespace, reason: str) -> int:
    if getattr(args, "json", False):
        payload = {
            "schemaVersion": 1,
            "status": "skipped",
            "reason": reason,
            "users": [{"status": "skipped", "reason": reason}],
            "apply_results": [],
        }
        print(json.dumps(payload, indent=2))
    else:
        print(f"memory hardening skipped: {reason}", file=sys.stderr)
    return 0


def node_command(args: argparse.Namespace, runtime_env: dict[str, str]) -> list[str]:
    script = args.repo_root / "viventium_v0_4" / "LibreChat" / "scripts" / "viventium-memory-hardening.js"
    node_mode = args.command
    if args.command == "ingest-transcripts":
        node_mode = "apply" if args.apply else "dry-run"
    command = [
        "node",
        str(script),
        "--mode",
        node_mode,
        "--app-support-dir",
        str(args.app_support_dir),
    ]
    if args.command == "ingest-transcripts":
        command.append("--transcripts-only")
    mongo_uri = args.mongo_uri or runtime_env.get("MONGO_URI")
    config_path = (
        args.config_path
        or runtime_env.get("CONFIG_PATH")
        or runtime_env.get("VIVENTIUM_CONFIG_PATH")
        or str(args.runtime_dir / "librechat.yaml")
    )
    if mongo_uri:
        command.extend(["--mongo-uri", mongo_uri])
    if config_path:
        command.extend(["--config-path", config_path])
    if args.run_id:
        command.extend(["--run-id", args.run_id])
    operator_user_email = user_email_for_run(args, runtime_env)
    if operator_user_email:
        command.extend(["--user-email", operator_user_email])
    if args.user_id:
        command.extend(["--user-id", args.user_id])
    if args.lookback_days is not None:
        command.extend(["--lookback-days", str(args.lookback_days)])
    if args.min_user_idle_minutes is not None:
        command.extend(["--min-user-idle-minutes", str(args.min_user_idle_minutes)])
    if args.max_changes_per_user is not None:
        command.extend(["--max-changes-per-user", str(args.max_changes_per_user)])
    elif args.command == "ingest-transcripts":
        command.extend(["--max-changes-per-user", "0"])
    if args.max_input_chars is not None:
        command.extend(["--max-input-chars", str(args.max_input_chars)])
    provider = args.provider or runtime_env.get("VIVENTIUM_MEMORY_HARDENING_PROVIDER")
    model = (
        args.model
        or (model_for_provider(args.provider, runtime_env) if args.provider else "")
        or runtime_env.get("VIVENTIUM_MEMORY_HARDENING_MODEL")
    )
    if provider:
        command.extend(["--provider", provider])
    if model:
        command.extend(["--model", model])
    if args.proposal_file:
        command.extend(["--proposal-file", args.proposal_file])
    if getattr(args, "transcripts_dir", None):
        command.extend(["--transcripts-dir", args.transcripts_dir])
    if getattr(args, "transcript_max_files_per_run", None) is not None:
        command.extend(["--transcript-max-files-per-run", str(args.transcript_max_files_per_run)])
    if getattr(args, "transcript_max_chars_per_file", None) is not None:
        command.extend(["--transcript-max-chars-per-file", str(args.transcript_max_chars_per_file)])
    if getattr(args, "transcript_summary_max_chars", None) is not None:
        command.extend(["--transcript-summary-max-chars", str(args.transcript_summary_max_chars)])
    if getattr(args, "transcript_reference_memory_max_chars", None) is not None:
        command.extend(
            [
                "--transcript-reference-memory-max-chars",
                str(args.transcript_reference_memory_max_chars),
            ]
        )
    if getattr(args, "transcript_reference_messages_max_chars", None) is not None:
        command.extend(
            [
                "--transcript-reference-messages-max-chars",
                str(args.transcript_reference_messages_max_chars),
            ]
        )
    transcript_rag_mode = getattr(args, "transcript_rag_mode", None) or runtime_env.get(
        "VIVENTIUM_MEMORY_TRANSCRIPTS_RAG_MODE"
    )
    if transcript_rag_mode:
        command.extend(["--transcript-rag-mode", transcript_rag_mode])
    if args.allow_delete:
        command.append("--allow-delete")
    if args.ignore_idle_gate:
        command.append("--ignore-idle-gate")
    if getattr(args, "ignore_efficiency_gate", False):
        command.append("--ignore-efficiency-gate")
    if getattr(args, "interactive_maintenance", False):
        command.append("--interactive-maintenance")
    if args.skip_model_probe:
        command.append("--skip-model-probe")
    if args.allow_partial_lookback:
        command.append("--allow-partial-lookback")
    if args.json:
        command.append("--json")
    return command


def transcript_backfill_skipped_by_cap(summary: dict[str, object]) -> int:
    skipped = 0
    for user in summary.get("users", []) if isinstance(summary.get("users"), list) else []:
        if not isinstance(user, dict):
            continue
        ingest = user.get("transcript_ingest") or {}
        if not isinstance(ingest, dict):
            continue
        skipped += int(ingest.get("files_skipped_by_cap") or 0)
    return skipped


def model_subprocess_kwargs(*, capture_output: bool) -> dict[str, object]:
    kwargs: dict[str, object] = {"text": True, "capture_output": capture_output}
    if hasattr(os, "nice"):
        kwargs["preexec_fn"] = lambda: os.nice(10)
    return kwargs


def run_node_once(args: argparse.Namespace, runtime_env: dict[str, str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        node_command(args, runtime_env),
        cwd=args.repo_root / "viventium_v0_4" / "LibreChat",
        env=env,
        **model_subprocess_kwargs(capture_output=True),
    )


def run_transcript_backfill_until_caught_up(
    args: argparse.Namespace, runtime_env: dict[str, str], env: dict[str, str]
) -> int:
    if not getattr(args, "apply", False):
        raise SystemExit("--until-caught-up requires --apply because dry-runs do not advance transcript state")
    max_batches = int(
        getattr(args, "max_batches", None)
        or env.get("VIVENTIUM_MEMORY_TRANSCRIPTS_MAX_BATCHES_PER_INVOCATION")
        or 1
    )
    if max_batches <= 0:
        raise SystemExit("--max-batches must be greater than 0")
    final_status = 0
    summaries: list[dict[str, object]] = []
    previous_skipped: int | None = None
    json_output = bool(getattr(args, "json", False))

    def emit_aggregate(status: str, reason: str | None = None) -> None:
        if not json_output and status == "complete":
            return
        latest = summaries[-1] if summaries else {}
        latest_skipped = transcript_backfill_skipped_by_cap(latest) if isinstance(latest, dict) else 0
        aggregate = {
            "schemaVersion": 1,
            "status": status,
            "reason": reason,
            "batches_run": len(summaries),
            "latest_run": latest.get("run_id") if isinstance(latest, dict) else None,
            "files_skipped_by_cap": latest_skipped,
            "batch_run_ids": [
                summary.get("run_id")
                for summary in summaries
                if isinstance(summary, dict) and summary.get("run_id")
            ],
            "users": latest.get("users", []) if isinstance(latest, dict) else [],
            "apply_results": latest.get("apply_results", []) if isinstance(latest, dict) else [],
        }
        print(json.dumps(aggregate, indent=2))

    for _ in range(max_batches):
        result = run_node_once(args, runtime_env, env)
        if result.stdout and not json_output:
            sys.stdout.write(result.stdout)
        if result.stderr:
            sys.stderr.write(result.stderr)
        final_status = int(result.returncode)
        if final_status != 0:
            if json_output and result.stdout:
                sys.stdout.write(result.stdout)
            return final_status
        try:
            summary = json.loads(result.stdout)
        except json.JSONDecodeError:
            if json_output and result.stdout:
                sys.stdout.write(result.stdout)
            return final_status
        summaries.append(summary)
        skipped = transcript_backfill_skipped_by_cap(summary)
        if skipped <= 0:
            emit_aggregate("complete")
            return final_status
        if previous_skipped is not None and skipped >= previous_skipped:
            emit_aggregate("partial", "no_batch_progress")
            return PARTIAL_BACKFILL_EXIT
        previous_skipped = skipped
    emit_aggregate("partial", "max_batches_reached")
    return PARTIAL_BACKFILL_EXIT


def run_node(args: argparse.Namespace, runtime_env: dict[str, str]) -> int:
    env = os.environ.copy()
    env.update(runtime_env)
    env["VIVENTIUM_APP_SUPPORT_DIR"] = str(args.app_support_dir)
    env.setdefault("VIVENTIUM_MEMORY_HARDENING_SCHEDULE", DEFAULT_SCHEDULE)
    env.setdefault("VIVENTIUM_MEMORY_HARDENING_TIMEZONE", DEFAULT_TIMEZONE)
    env.setdefault("VIVENTIUM_MEMORY_HARDENING_PROVIDER", env.get("VIVENTIUM_MEMORY_HARDENING_PROVIDER", ""))
    env.setdefault("VIVENTIUM_MEMORY_HARDENING_MODEL", env.get("VIVENTIUM_MEMORY_HARDENING_MODEL", ""))
    env.setdefault("VIVENTIUM_MEMORY_HARDENING_EFFORT", "xhigh")
    env.setdefault("VIVENTIUM_MEMORY_HARDENING_ANTHROPIC_EFFORT", env["VIVENTIUM_MEMORY_HARDENING_EFFORT"])
    env.setdefault("VIVENTIUM_MEMORY_HARDENING_OPENAI_REASONING_EFFORT", env["VIVENTIUM_MEMORY_HARDENING_EFFORT"])
    trigger_event = start_trigger_event(args, env)
    skip_reason = power_gate_skip_reason(args, env)
    if skip_reason:
        return finish_trigger_event(
            trigger_event,
            args,
            emit_resource_gate_skip(args, skip_reason),
            status="skipped",
            reason=skip_reason,
        )
    scheduled_apply = args.command == "apply" or (
        args.command == "ingest-transcripts" and getattr(args, "apply", False)
    )
    if (
        scheduled_apply
        and getattr(args, "scheduled", False)
        and env.get("VIVENTIUM_MEMORY_HARDENING_DRY_RUN_FIRST", "true").lower()
        in {"1", "true", "yes", "on"}
    ):
        marker = args.app_support_dir / "state" / "memory-hardening" / "dry-run-first-complete"
        if not marker.exists():
            if args.command == "ingest-transcripts":
                args.apply = False
            else:
                args.command = "dry-run"
            result = subprocess.run(
                node_command(args, runtime_env),
                cwd=args.repo_root / "viventium_v0_4" / "LibreChat",
                env=env,
                **model_subprocess_kwargs(capture_output=False),
            )
            if result.returncode == 0:
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text("completed\n", encoding="utf-8")
            return finish_trigger_event(trigger_event, args, int(result.returncode))
    if args.command == "ingest-transcripts" and getattr(args, "until_caught_up", False):
        return finish_trigger_event(
            trigger_event,
            args,
            run_transcript_backfill_until_caught_up(args, runtime_env, env),
        )
    command = node_command(args, runtime_env)
    process = subprocess.run(
        command,
        cwd=args.repo_root / "viventium_v0_4" / "LibreChat",
        env=env,
        **model_subprocess_kwargs(capture_output=False),
    )
    return finish_trigger_event(trigger_event, args, int(process.returncode))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local Viventium saved-memory hardening.")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--app-support-dir", type=Path, required=True)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--mongo-uri")
    parser.add_argument("--config-path")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("dry-run", "apply", "rollback", "status"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--run-id")
        sub.add_argument("--user-email")
        sub.add_argument("--user-id")
        sub.add_argument("--lookback-days", type=int)
        sub.add_argument("--min-user-idle-minutes", type=int)
        sub.add_argument("--max-changes-per-user", type=int)
        sub.add_argument("--max-input-chars", type=int)
        sub.add_argument("--provider")
        sub.add_argument("--model")
        sub.add_argument("--proposal-file")
        sub.add_argument("--transcripts-dir")
        sub.add_argument("--transcript-max-files-per-run", type=int)
        sub.add_argument("--transcript-max-chars-per-file", type=int)
        sub.add_argument("--transcript-summary-max-chars", type=int)
        sub.add_argument("--transcript-reference-memory-max-chars", type=int)
        sub.add_argument("--transcript-reference-messages-max-chars", type=int)
        sub.add_argument("--transcript-rag-mode")
        sub.add_argument("--allow-delete", action="store_true")
        sub.add_argument("--ignore-idle-gate", action="store_true")
        sub.add_argument("--ignore-power-gate", action="store_true")
        sub.add_argument("--ignore-efficiency-gate", action="store_true")
        sub.add_argument("--interactive-maintenance", action="store_true")
        sub.add_argument("--skip-model-probe", action="store_true")
        sub.add_argument("--allow-partial-lookback", action="store_true")
        sub.add_argument("--scheduled", action="store_true")
        sub.add_argument("--trigger")
        sub.add_argument("--json", action="store_true")
    ingest = subparsers.add_parser("ingest-transcripts")
    ingest_mode = ingest.add_mutually_exclusive_group()
    ingest_mode.add_argument("--dry-run", action="store_true", default=True)
    ingest_mode.add_argument("--apply", action="store_true")
    ingest.add_argument("--run-id")
    ingest.add_argument("--user-email")
    ingest.add_argument("--user-id")
    ingest.add_argument("--lookback-days", type=int)
    ingest.add_argument("--min-user-idle-minutes", type=int)
    ingest.add_argument("--max-changes-per-user", type=int)
    ingest.add_argument("--max-input-chars", type=int)
    ingest.add_argument("--provider")
    ingest.add_argument("--model")
    ingest.add_argument("--proposal-file")
    ingest.add_argument("--transcripts-dir")
    ingest.add_argument("--transcript-max-files-per-run", type=int)
    ingest.add_argument("--transcript-max-chars-per-file", type=int)
    ingest.add_argument("--transcript-summary-max-chars", type=int)
    ingest.add_argument("--transcript-reference-memory-max-chars", type=int)
    ingest.add_argument("--transcript-reference-messages-max-chars", type=int)
    ingest.add_argument("--transcript-rag-mode")
    ingest.add_argument("--until-caught-up", action="store_true")
    ingest.add_argument("--max-batches", type=int)
    ingest.add_argument("--allow-delete", action="store_true")
    ingest.add_argument("--ignore-idle-gate", action="store_true")
    ingest.add_argument("--ignore-power-gate", action="store_true")
    ingest.add_argument("--ignore-efficiency-gate", action="store_true")
    ingest.add_argument("--interactive-maintenance", action="store_true")
    ingest.add_argument("--skip-model-probe", action="store_true")
    ingest.add_argument("--allow-partial-lookback", action="store_true")
    ingest.add_argument("--scheduled", action="store_true")
    ingest.add_argument("--trigger")
    ingest.add_argument("--json", action="store_true")
    install = subparsers.add_parser("install-schedule")
    install.add_argument("--schedule")
    install.add_argument("--user-email")
    install.add_argument("--json", action="store_true")
    uninstall = subparsers.add_parser("uninstall-schedule")
    uninstall.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.repo_root = args.repo_root.resolve()
    args.app_support_dir = args.app_support_dir.expanduser().resolve()
    args.runtime_dir = args.runtime_dir.expanduser().resolve()
    librechat_dir = args.repo_root / "viventium_v0_4" / "LibreChat"
    runtime_env = load_runtime_env(args.runtime_dir, librechat_dir)
    (args.app_support_dir / "logs").mkdir(parents=True, exist_ok=True)

    if args.command == "install-schedule":
        result = install_schedule(args, runtime_env)
        print(json.dumps(result, indent=2))
        return 0
    if args.command == "uninstall-schedule":
        result = uninstall_schedule(args)
        print(json.dumps(result, indent=2))
        return 0
    return run_node(args, runtime_env)


if __name__ == "__main__":
    raise SystemExit(main())
