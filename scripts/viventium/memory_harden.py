#!/usr/bin/env python3
"""Local operator wrapper for Viventium saved-memory hardening."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
import plistlib
import pwd
import re
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows does not install LaunchAgents.
    fcntl = None  # type: ignore[assignment]


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import power_budget


DEFAULT_SCHEDULE = "0 3 * * *"
DEFAULT_TIMEZONE = "local"
LAUNCH_AGENT_LABEL = "ai.viventium.memory-harden"
LAUNCHCTL_PATH = "/bin/launchctl"
PARTIAL_BACKFILL_EXIT = 2
TRIGGER_EVENT_SCHEMA_VERSION = 3
SCHEDULE_V3_OBSERVATION_SCHEMA_VERSION = 1
SCHEDULE_LIFECYCLE_SCHEMA_VERSION = 1
DEFAULT_OPENAI_MEMORY_EFFORT_BY_MODEL = {
    "gpt-5.5": "xhigh",
    "gpt-5.6-sol": "xhigh",
    "gpt-5.6-terra": "high",
    "gpt-5.6-luna": "medium",
}
DEFAULT_OPENAI_MEMORY_EFFORT = "high"


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


def _valid_timezone_name(value: str) -> bool:
    try:
        ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError):
        return False
    return True


def local_timezone_name() -> str:
    for candidate_path in (Path("/etc/localtime"), Path("/var/db/timezone/localtime")):
        try:
            resolved = os.path.realpath(candidate_path)
        except OSError:
            continue
        marker = "/zoneinfo/"
        if marker in resolved:
            candidate = resolved.split(marker, 1)[1]
            if _valid_timezone_name(candidate):
                return candidate

    try:
        candidate = Path("/etc/timezone").read_text(encoding="utf-8").strip()
    except OSError:
        candidate = ""
    if candidate and _valid_timezone_name(candidate):
        return candidate

    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["/usr/sbin/systemsetup", "-gettimezone"],
                text=True,
                capture_output=True,
                check=False,
                timeout=2,
            )
        except (OSError, subprocess.TimeoutExpired):
            result = None
        match = re.search(r"Time Zone:\s*(\S+)", result.stdout if result else "")
        if match and _valid_timezone_name(match.group(1)):
            return match.group(1)

    tzinfo = datetime.now().astimezone().tzinfo
    candidate = str(getattr(tzinfo, "key", "") or getattr(tzinfo, "zone", "")).strip()
    return candidate if candidate and _valid_timezone_name(candidate) else "UTC"


def configured_timezone(env: dict[str, str]) -> tuple[str, object]:
    name = str(env.get("VIVENTIUM_MEMORY_HARDENING_TIMEZONE") or DEFAULT_TIMEZONE).strip()
    if not name or name.lower() in {"local", "system", "auto"}:
        name = local_timezone_name()
    try:
        return name, ZoneInfo(name)
    except (ValueError, ZoneInfoNotFoundError):
        fallback = local_timezone_name()
        return fallback, ZoneInfo(fallback)


def public_hash(value: object, length: int = 16) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:length]


def trigger_events_dir(app_support_dir: Path) -> Path:
    return app_support_dir / "state" / "memory-hardening" / "schedule-events"


def schedule_v3_observation_path(app_support_dir: Path) -> Path:
    return app_support_dir / "state" / "memory-hardening" / "schedule-v3-observed.public.json"


def launchd_invocation_proof(args: argparse.Namespace) -> dict[str, object]:
    """Bind the running process to the loaded LaunchAgent's current job PID.

    This protects cadence health from ordinary manual calls, labels, and orphan/double-forked
    processes. The local logged-in operator still owns launchd and the receipt store; resisting a
    malicious local administrator is intentionally outside this local-user trust boundary.
    """
    cached = getattr(args, "_launchd_invocation_proof", None)
    if isinstance(cached, dict):
        return cached
    proof: dict[str, object] = {
        "version": 1,
        "method": "launchctl_job_pid",
        "verified": False,
        "label": LAUNCH_AGENT_LABEL,
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
        "launchctl_status": "not_checked",
    }
    if not getattr(args, "scheduled", False):
        proof["launchctl_status"] = "scheduled_flag_missing"
    elif sys.platform != "darwin":
        proof["launchctl_status"] = "unsupported_platform"
    elif os.getppid() != 1:
        proof["launchctl_status"] = "parent_not_launchd"
    else:
        try:
            completed = subprocess.run(
                [LAUNCHCTL_PATH, "print", f"gui/{os.getuid()}/{LAUNCH_AGENT_LABEL}"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            proof["launchctl_status"] = "query_failed"
        else:
            match = re.search(r"^\s*pid\s*=\s*(\d+)\s*$", completed.stdout or "", re.MULTILINE)
            observed_pid = int(match.group(1)) if match else None
            proof["launchctl_status"] = "ok" if completed.returncode == 0 else "job_unavailable"
            proof["observed_job_pid"] = observed_pid
            proof["verified"] = bool(
                completed.returncode == 0 and observed_pid == os.getpid()
            )
    setattr(args, "_launchd_invocation_proof", proof)
    return proof


def is_verified_launchd_invocation(args: argparse.Namespace) -> bool:
    """Return true only when launchd, rather than a caller label, owns this run."""
    return bool(launchd_invocation_proof(args).get("verified"))


def trigger_source_for_args(args: argparse.Namespace) -> str:
    explicit = str(getattr(args, "trigger", "") or "").strip().lower()
    if explicit == "launchd":
        return "launchd" if is_verified_launchd_invocation(args) else "launchd_unverified"
    if explicit:
        return explicit
    if getattr(args, "scheduled", False):
        return "scheduled_legacy"
    return ""


def trigger_schedule_payload(env: dict[str, str]) -> dict[str, object]:
    schedule = env.get("VIVENTIUM_MEMORY_HARDENING_SCHEDULE") or DEFAULT_SCHEDULE
    configured_timezone_name, _tzinfo = configured_timezone(env)
    payload: dict[str, object] = {
        "kind": "StartCalendarInterval",
        "cron": schedule,
        "timezone_source": "system",
        "system_timezone": local_timezone_name(),
        "generated_runtime_timezone": configured_timezone_name,
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
    local_fired_at = fired_at.astimezone(ZoneInfo(local_timezone_name()))
    event_id = f"{trigger_source}-{fired_at.strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}"
    trigger_proof = (
        launchd_invocation_proof(args)
        if str(getattr(args, "trigger", "") or "").strip().lower() == "launchd"
        else {
            "version": 1,
            "method": "none",
            "verified": False,
            "launchctl_status": "not_applicable",
        }
    )
    payload: dict[str, object] = {
        "schemaVersion": TRIGGER_EVENT_SCHEMA_VERSION,
        "event_id": event_id,
        "status": "started",
        "trigger_source": trigger_source,
        "trigger_claim": str(getattr(args, "trigger", "") or "").strip().lower(),
        "trigger_proof": trigger_proof,
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
        "requested_provider": str(env.get("VIVENTIUM_MEMORY_HARDENING_PROVIDER") or "").strip(),
        "requested_model": str(env.get("VIVENTIUM_MEMORY_HARDENING_MODEL") or "").strip(),
        "requested_effort": str(env.get("VIVENTIUM_MEMORY_HARDENING_EFFORT") or "").strip(),
    }
    path = trigger_events_dir(args.app_support_dir) / f"{event_id}.json"
    write_json_private(path, payload)
    if trigger_source == "launchd" and TRIGGER_EVENT_SCHEMA_VERSION >= 3:
        observation_path = schedule_v3_observation_path(args.app_support_dir)
        if not observation_path.exists():
            write_json_private(
                observation_path,
                {
                    "schemaVersion": SCHEDULE_V3_OBSERVATION_SCHEMA_VERSION,
                    "observedReceiptSchemaVersion": TRIGGER_EVENT_SCHEMA_VERSION,
                    "firstObservedAtUtc": iso_z(fired_at),
                },
            )
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
        payload["effective_provider"] = latest_summary.get("provider")
        payload["effective_model"] = latest_summary.get("model")
        payload["effective_effort"] = latest_summary.get("effort")
    write_json_private(path, payload)
    return exit_code


def canonical_user_home() -> Path:
    return Path(pwd.getpwuid(os.getuid()).pw_dir).expanduser()


def launch_agent_path() -> Path:
    return canonical_user_home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def canonical_app_support_dir() -> Path:
    """Resolve the one user-level runtime root independently of a spoofed HOME."""
    return canonical_user_home() / "Library" / "Application Support" / "Viventium"


def require_canonical_schedule_scope(args: argparse.Namespace) -> None:
    requested = Path(args.app_support_dir).expanduser().resolve(strict=False)
    canonical = canonical_app_support_dir().resolve(strict=False)
    if requested != canonical:
        raise SystemExit(
            "memory-hardening LaunchAgent schedule changes require the canonical "
            "Viventium App Support root"
        )


def schedule_lifecycle_events_dir(app_support_dir: Path) -> Path:
    return app_support_dir / "state" / "memory-hardening" / "schedule-lifecycle"


@contextmanager
def schedule_loader_lock(app_support_dir: Path):
    if fcntl is None:
        yield
        return
    lock_path = app_support_dir / "state" / "memory-hardening" / "schedule-loader.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def launch_agent_target() -> str:
    return f"gui/{os.getuid()}/{LAUNCH_AGENT_LABEL}"


def launch_agent_loaded() -> tuple[bool, subprocess.CompletedProcess[str]]:
    result = subprocess.run(
        [LAUNCHCTL_PATH, "print", launch_agent_target()],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0, result


def read_launch_agent_payload(plist_path: Path) -> dict[str, object] | None:
    if not plist_path.exists():
        return None
    try:
        with plist_path.open("rb") as handle:
            payload = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException):
        return None
    return payload if isinstance(payload, dict) else None


def snapshot_regular_file(path: Path) -> dict[str, object]:
    """Capture exact restorable bytes without following a user-controlled symlink."""
    if path.is_symlink():
        raise SystemExit(f"refusing to reconcile unsafe symlink: {path}")
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return {"installed": False, "bytes": None, "mode": None}
    if not stat.S_ISREG(metadata.st_mode):
        raise SystemExit(f"refusing to reconcile non-regular file: {path}")
    if metadata.st_uid != os.getuid():
        raise SystemExit(f"refusing to reconcile file not owned by the current user: {path}")
    return {
        "installed": True,
        "bytes": path.read_bytes(),
        "mode": stat.S_IMODE(metadata.st_mode),
    }


def write_regular_file_atomic(path: Path, payload: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp-{os.getpid()}-{time.time_ns()}")
    try:
        with temporary_path.open("wb") as handle:
            handle.write(payload)
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def restore_regular_file_snapshot(path: Path, snapshot: dict[str, object]) -> None:
    installed = snapshot.get("installed") is True
    if not installed:
        if path.is_symlink():
            raise RuntimeError(f"refusing to remove unsafe symlink while restoring {path}")
        if path.exists():
            snapshot_regular_file(path)
            path.unlink()
        return
    payload = snapshot.get("bytes")
    mode = snapshot.get("mode")
    if not isinstance(payload, bytes) or not isinstance(mode, int):
        raise RuntimeError(f"invalid file snapshot for {path}")
    if path.is_symlink():
        raise RuntimeError(f"refusing to replace unsafe symlink while restoring {path}")
    if path.exists():
        snapshot_regular_file(path)
    write_regular_file_atomic(path, payload, mode)


def regular_file_snapshot_matches(path: Path, snapshot: dict[str, object]) -> bool:
    try:
        return snapshot_regular_file(path) == snapshot
    except (OSError, SystemExit):
        return False


def capture_launch_agent_snapshot(plist_path: Path) -> dict[str, object]:
    file_snapshot = snapshot_regular_file(plist_path)
    loaded, _probe = launch_agent_loaded()
    if loaded and file_snapshot.get("installed") is not True:
        raise SystemExit(
            "refusing to mutate a loaded memory hardening LaunchAgent without a restorable plist"
        )
    return {"file": file_snapshot, "loaded": loaded}


def restore_launch_agent_snapshot(
    plist_path: Path,
    snapshot: dict[str, object],
) -> tuple[bool, str | None]:
    file_snapshot = snapshot.get("file")
    prior_loaded = snapshot.get("loaded") is True
    if not isinstance(file_snapshot, dict):
        return False, "invalid_launch_agent_snapshot"
    try:
        current_loaded, _probe = launch_agent_loaded()
        if regular_file_snapshot_matches(plist_path, file_snapshot) and current_loaded == prior_loaded:
            return True, None

        if current_loaded:
            bootout = subprocess.run(
                [LAUNCHCTL_PATH, "bootout", launch_agent_target()],
                check=False,
                capture_output=True,
                text=True,
            )
            still_loaded, _verify = launch_agent_loaded()
            if bootout.returncode != 0 or still_loaded:
                return False, "rollback_launchctl_bootout_failed"

        restore_regular_file_snapshot(plist_path, file_snapshot)
        if prior_loaded:
            if file_snapshot.get("installed") is not True:
                return False, "rollback_missing_prior_plist"
            bootstrap = subprocess.run(
                [LAUNCHCTL_PATH, "bootstrap", f"gui/{os.getuid()}", str(plist_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            restored_loaded, _verify = launch_agent_loaded()
            if bootstrap.returncode != 0 or not restored_loaded:
                return False, "rollback_launchctl_bootstrap_failed"
        else:
            restored_loaded, _verify = launch_agent_loaded()
            if restored_loaded:
                return False, "rollback_launchctl_verify_failed"

        if not regular_file_snapshot_matches(plist_path, file_snapshot):
            return False, "rollback_plist_verify_failed"
        return True, None
    except BaseException as error:
        return False, f"rollback_{type(error).__name__}"


def desired_launch_agent_payload(
    args: argparse.Namespace,
    runtime_env: dict[str, str],
    schedule: str,
) -> dict[str, object]:
    hour, minute = cron_to_launchd_time(schedule)
    user_home = canonical_user_home()
    logs_dir = args.app_support_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    launch_path = ":".join(
        [
            str(Path.home() / ".local" / "bin"),
            str(Path.home() / ".codex" / "bin"),
            "/Applications/ChatGPT.app/Contents/Resources",
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
        f"HOME={str(user_home)}",
        f"USER={os.environ.get('USER', '')}",
        f"LOGNAME={os.environ.get('LOGNAME', os.environ.get('USER', ''))}",
        "SHELL=/bin/zsh",
        f"PATH={launch_path}",
        "LANG=en_US.UTF-8",
        "LC_ALL=en_US.UTF-8",
        str(Path(sys.executable).resolve()),
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
    return {
        "Label": LAUNCH_AGENT_LABEL,
        "ProgramArguments": program_arguments,
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "StandardOutPath": str(logs_dir / "memory-hardening.log"),
        "StandardErrorPath": str(logs_dir / "memory-hardening.err.log"),
        "WorkingDirectory": str(args.app_support_dir),
        "RunAtLoad": False,
    }


def launch_agent_generation_hash(payload: dict[str, object]) -> str:
    encoded = plistlib.dumps(payload, sort_keys=True)
    return hashlib.sha256(encoded).hexdigest()[:16]


def write_launch_agent_payload(plist_path: Path, payload: dict[str, object]) -> None:
    write_regular_file_atomic(plist_path, plistlib.dumps(payload, sort_keys=True), 0o644)


def write_schedule_lifecycle_receipt(
    args: argparse.Namespace,
    *,
    action: str,
    status: str,
    schedule: str,
    desired_payload: dict[str, object],
    prior_installed: bool,
    prior_loaded: bool,
    loaded_verified: bool,
    bootout_returncode: int | None = None,
    bootstrap_returncode: int | None = None,
    error_class: str | None = None,
    rollback_status: str | None = None,
    rollback_error_class: str | None = None,
) -> Path:
    now = utc_now()
    hour, minute = cron_to_launchd_time(schedule)
    event_id = f"event-{now.strftime('%Y%m%dT%H%M%S%fZ')}-{os.getpid()}-{time.time_ns()}"
    payload: dict[str, object] = {
        "schemaVersion": SCHEDULE_LIFECYCLE_SCHEMA_VERSION,
        "event_id": event_id,
        "recorded_at_utc": iso_z(now),
        "recorded_at_local": now.astimezone(ZoneInfo(local_timezone_name())).isoformat(
            timespec="milliseconds"
        ),
        "action": action,
        "status": status,
        "label": LAUNCH_AGENT_LABEL,
        "schedule": {
            "kind": "StartCalendarInterval",
            "cron": schedule,
            "hour": hour,
            "minute": minute,
            "timezone_source": "system",
        },
        "generation_hash": launch_agent_generation_hash(desired_payload),
        "prior_installed": prior_installed,
        "prior_loaded": prior_loaded,
        "loaded_verified": loaded_verified,
        "bootout_returncode": bootout_returncode,
        "bootstrap_returncode": bootstrap_returncode,
    }
    if error_class:
        payload["error_class"] = error_class
    if rollback_status:
        payload["rollback_status"] = rollback_status
    if rollback_error_class:
        payload["rollback_error_class"] = rollback_error_class
    events_dir = schedule_lifecycle_events_dir(args.app_support_dir)
    event_path = events_dir / f"{event_id}.json"
    write_json_private(event_path, payload)
    write_json_private(events_dir / "latest.json", payload)
    return event_path


def schedule_install_result(
    *,
    schedule: str,
    runtime_env: dict[str, str],
    plist_path: Path,
    action: str,
    loaded: bool,
) -> dict[str, object]:
    configured_timezone_name, _tzinfo = configured_timezone(runtime_env)
    return {
        "installed": True,
        "loaded": loaded,
        "changed": action != "noop",
        "action": action,
        "label": LAUNCH_AGENT_LABEL,
        "schedule": schedule,
        "timezone": local_timezone_name(),
        "timezone_source": "system",
        "generated_runtime_timezone": configured_timezone_name,
        "plist": str(plist_path),
    }


def _install_schedule_locked(args: argparse.Namespace, runtime_env: dict[str, str]) -> dict[str, object]:
    if sys.platform != "darwin":
        raise SystemExit("install-schedule currently supports macOS LaunchAgents. Use cron/systemd on Linux.")
    schedule = args.schedule or runtime_env.get("VIVENTIUM_MEMORY_HARDENING_SCHEDULE") or DEFAULT_SCHEDULE
    cron_to_launchd_time(schedule)
    plist_path = launch_agent_path()
    desired_payload = desired_launch_agent_payload(args, runtime_env, schedule)
    prior_snapshot = capture_launch_agent_snapshot(plist_path)
    current_payload = read_launch_agent_payload(plist_path)
    prior_file_snapshot = prior_snapshot["file"]
    if not isinstance(prior_file_snapshot, dict):
        raise SystemExit("could not capture the prior memory hardening LaunchAgent")
    prior_installed = prior_file_snapshot.get("installed") is True
    prior_loaded = prior_snapshot.get("loaded") is True
    payload_matches = current_payload == desired_payload

    if payload_matches and prior_loaded:
        write_schedule_lifecycle_receipt(
            args,
            action="noop",
            status="success",
            schedule=schedule,
            desired_payload=desired_payload,
            prior_installed=prior_installed,
            prior_loaded=prior_loaded,
            loaded_verified=True,
        )
        return schedule_install_result(
            schedule=schedule,
            runtime_env=runtime_env,
            plist_path=plist_path,
            action="noop",
            loaded=True,
        )

    action = "bootstrap" if payload_matches else ("reinstall" if prior_installed or prior_loaded else "install")
    bootout_returncode: int | None = None
    bootstrap_returncode: int | None = None
    loaded_verified = False
    failure_phase = "schedule_reconcile_failed"
    try:
        if prior_loaded and not payload_matches:
            failure_phase = "launchctl_bootout_failed"
            bootout = subprocess.run(
                [LAUNCHCTL_PATH, "bootout", launch_agent_target()],
                check=False,
                capture_output=True,
                text=True,
            )
            bootout_returncode = int(bootout.returncode)
            still_loaded, _ = launch_agent_loaded()
            if bootout.returncode != 0 or still_loaded:
                raise SystemExit("failed to unload the previous memory hardening LaunchAgent")

        if not payload_matches:
            failure_phase = "plist_write_failed"
            write_launch_agent_payload(plist_path, desired_payload)

        failure_phase = "launchctl_bootstrap_failed"
        bootstrap = subprocess.run(
            [LAUNCHCTL_PATH, "bootstrap", f"gui/{os.getuid()}", str(plist_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        bootstrap_returncode = int(bootstrap.returncode)
        loaded_verified, _verify = launch_agent_loaded()
        if bootstrap.returncode != 0 or not loaded_verified:
            failure_phase = (
                "launchctl_bootstrap_failed"
                if bootstrap.returncode != 0
                else "launchctl_verify_failed"
            )
            detail = (bootstrap.stderr or bootstrap.stdout or "").strip()
            raise SystemExit(
                "failed to install memory hardening LaunchAgent"
                + (f": {detail}" if detail else "")
            )

        failure_phase = "receipt_write_failed"
        write_schedule_lifecycle_receipt(
            args,
            action=action,
            status="success",
            schedule=schedule,
            desired_payload=desired_payload,
            prior_installed=prior_installed,
            prior_loaded=prior_loaded,
            loaded_verified=True,
            bootout_returncode=bootout_returncode,
            bootstrap_returncode=bootstrap_returncode,
        )
    except BaseException:
        rollback_restored, rollback_error_class = restore_launch_agent_snapshot(
            plist_path,
            prior_snapshot,
        )
        try:
            write_schedule_lifecycle_receipt(
                args,
                action=action,
                status="failed",
                schedule=schedule,
                desired_payload=desired_payload,
                prior_installed=prior_installed,
                prior_loaded=prior_loaded,
                loaded_verified=loaded_verified,
                bootout_returncode=bootout_returncode,
                bootstrap_returncode=bootstrap_returncode,
                error_class=failure_phase,
                rollback_status="restored" if rollback_restored else "failed",
                rollback_error_class=rollback_error_class,
            )
        except BaseException:
            pass
        if not rollback_restored:
            raise SystemExit(
                "memory hardening LaunchAgent reconciliation failed and the prior state "
                f"could not be restored ({rollback_error_class or 'unknown rollback error'})"
            )
        raise
    return schedule_install_result(
        schedule=schedule,
        runtime_env=runtime_env,
        plist_path=plist_path,
        action=action,
        loaded=True,
    )


def install_schedule(args: argparse.Namespace, runtime_env: dict[str, str]) -> dict[str, object]:
    if sys.platform != "darwin":
        raise SystemExit("install-schedule currently supports macOS LaunchAgents. Use cron/systemd on Linux.")
    require_canonical_schedule_scope(args)
    with schedule_loader_lock(args.app_support_dir):
        return _install_schedule_locked(args, runtime_env)


def _uninstall_schedule_locked(args: argparse.Namespace) -> dict[str, object]:
    plist_path = launch_agent_path()
    prior_snapshot = capture_launch_agent_snapshot(plist_path) if sys.platform == "darwin" else {
        "file": snapshot_regular_file(plist_path),
        "loaded": False,
    }
    prior_file_snapshot = prior_snapshot["file"]
    if not isinstance(prior_file_snapshot, dict):
        raise SystemExit("could not capture the prior memory hardening LaunchAgent")
    prior_bytes = prior_file_snapshot.get("bytes")
    try:
        parsed_prior = plistlib.loads(prior_bytes) if isinstance(prior_bytes, bytes) else None
    except plistlib.InvalidFileException:
        parsed_prior = None
    current_payload = parsed_prior if isinstance(parsed_prior, dict) else {
        "Label": LAUNCH_AGENT_LABEL,
        "StartCalendarInterval": {"Hour": 0, "Minute": 0},
    }
    schedule = DEFAULT_SCHEDULE
    calendar = current_payload.get("StartCalendarInterval")
    if isinstance(calendar, dict):
        schedule = f"{int(calendar.get('Minute') or 0)} {int(calendar.get('Hour') or 0)} * * *"
    prior_installed = prior_file_snapshot.get("installed") is True
    prior_loaded = prior_snapshot.get("loaded") is True
    marker = args.app_support_dir / "state" / "memory-hardening" / "dry-run-first-complete"
    marker_snapshot = snapshot_regular_file(marker)
    bootout_returncode: int | None = None
    action = (
        "uninstall"
        if prior_installed or prior_loaded or marker_snapshot.get("installed") is True
        else "noop"
    )
    failure_phase = "schedule_uninstall_failed"
    try:
        if prior_loaded:
            failure_phase = "launchctl_bootout_failed"
            bootout = subprocess.run(
                [LAUNCHCTL_PATH, "bootout", launch_agent_target()],
                check=False,
                capture_output=True,
                text=True,
            )
            bootout_returncode = int(bootout.returncode)
            still_loaded, _ = launch_agent_loaded()
            if bootout.returncode != 0 or still_loaded:
                raise SystemExit("failed to unload the memory hardening LaunchAgent")
        failure_phase = "plist_remove_failed"
        if plist_path.exists():
            plist_path.unlink()
        failure_phase = "marker_remove_failed"
        if marker.exists():
            marker.unlink()
        failure_phase = "receipt_write_failed"
        write_schedule_lifecycle_receipt(
            args,
            action=action,
            status="success",
            schedule=schedule,
            desired_payload=current_payload,
            prior_installed=prior_installed,
            prior_loaded=prior_loaded,
            loaded_verified=False,
            bootout_returncode=bootout_returncode,
        )
    except BaseException:
        rollback_restored, rollback_error_class = restore_launch_agent_snapshot(
            plist_path,
            prior_snapshot,
        )
        try:
            restore_regular_file_snapshot(marker, marker_snapshot)
        except BaseException as marker_error:
            rollback_restored = False
            rollback_error_class = f"rollback_marker_{type(marker_error).__name__}"
        try:
            write_schedule_lifecycle_receipt(
                args,
                action="uninstall",
                status="failed",
                schedule=schedule,
                desired_payload=current_payload,
                prior_installed=prior_installed,
                prior_loaded=prior_loaded,
                loaded_verified=False,
                bootout_returncode=bootout_returncode,
                error_class=failure_phase,
                rollback_status="restored" if rollback_restored else "failed",
                rollback_error_class=rollback_error_class,
            )
        except BaseException:
            pass
        if not rollback_restored:
            raise SystemExit(
                "memory hardening LaunchAgent uninstall failed and the prior state "
                f"could not be restored ({rollback_error_class or 'unknown rollback error'})"
            )
        raise
    return {
        "installed": False,
        "loaded": False,
        "changed": action != "noop",
        "action": action,
        "label": LAUNCH_AGENT_LABEL,
        "plist": str(plist_path),
    }


def uninstall_schedule(args: argparse.Namespace) -> dict[str, object]:
    require_canonical_schedule_scope(args)
    with schedule_loader_lock(args.app_support_dir):
        return _uninstall_schedule_locked(args)


def model_for_provider(provider: str | None, runtime_env: dict[str, str]) -> str:
    normalized = str(provider or "").strip().lower().replace("-", "_")
    if normalized in {"anthropic", "claude", "claude_code"}:
        return runtime_env.get("VIVENTIUM_MEMORY_HARDENING_ANTHROPIC_MODEL", "")
    if normalized in {"openai", "openai_api", "codex"}:
        return runtime_env.get("VIVENTIUM_MEMORY_HARDENING_OPENAI_MODEL", "")
    return ""


def normalize_memory_provider(provider: str | None) -> str:
    normalized = str(provider or "").strip().lower().replace("-", "_")
    if normalized in {"anthropic", "claude", "claude_code"}:
        return "anthropic"
    if normalized in {"openai", "openai_api", "codex"}:
        return "openai"
    return normalized


def default_memory_hardening_effort(args: argparse.Namespace, env: dict[str, str]) -> str:
    provider = normalize_memory_provider(
        getattr(args, "provider", None) or env.get("VIVENTIUM_MEMORY_HARDENING_PROVIDER")
    )
    if not provider:
        configured_providers = {
            normalize_memory_provider(env.get("VIVENTIUM_PRIMARY_PROVIDER")),
            normalize_memory_provider(env.get("VIVENTIUM_SECONDARY_PROVIDER")),
        }
        if "openai" in configured_providers:
            provider = "openai"
        elif "anthropic" in configured_providers:
            provider = "anthropic"
        else:
            provider = "openai"

    model = str(getattr(args, "model", None) or "").strip()
    if not model:
        explicit_provider = getattr(args, "provider", None)
        model = (
            (model_for_provider(explicit_provider, env) if explicit_provider else "")
            or str(env.get("VIVENTIUM_MEMORY_HARDENING_MODEL") or "").strip()
            or model_for_provider(provider, env)
        )
    if not model:
        model = "gpt-5.6-luna" if provider == "openai" else "claude-opus-5"
    if provider == "openai":
        return DEFAULT_OPENAI_MEMORY_EFFORT_BY_MODEL.get(
            model,
            DEFAULT_OPENAI_MEMORY_EFFORT,
        )
    return "xhigh"


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


def model_subprocess_kwargs(
    *, capture_output: bool, lower_priority: bool = True
) -> dict[str, object]:
    kwargs: dict[str, object] = {"text": True, "capture_output": capture_output}
    if lower_priority and hasattr(os, "nice"):
        kwargs["preexec_fn"] = lambda: os.nice(10)
    return kwargs


def launch_agent_status(runtime_env: dict[str, str]) -> dict[str, object]:
    plist_path = launch_agent_path()
    payload = read_launch_agent_payload(plist_path) or {}
    loaded = False
    state = None
    last_exit_code = None
    if sys.platform == "darwin":
        loaded, result = launch_agent_loaded()
        if loaded:
            state_match = re.search(r"\bstate\s*=\s*([^\n]+)", result.stdout)
            exit_match = re.search(r"\blast exit code\s*=\s*(-?\d+)", result.stdout)
            state = state_match.group(1).strip() if state_match else None
            last_exit_code = int(exit_match.group(1)) if exit_match else None
    configured_timezone_name, _tzinfo = configured_timezone(runtime_env)
    latest_lifecycle: dict[str, object] | None = None
    app_support_text = runtime_env.get("VIVENTIUM_APP_SUPPORT_DIR")
    if app_support_text:
        latest_path = schedule_lifecycle_events_dir(Path(app_support_text)) / "latest.json"
        try:
            decoded = json.loads(latest_path.read_text(encoding="utf-8"))
            latest_lifecycle = decoded if isinstance(decoded, dict) else None
        except (OSError, json.JSONDecodeError):
            latest_lifecycle = None
    return {
        "installed": plist_path.exists(),
        "loaded": loaded,
        "state": state,
        "last_exit_code": last_exit_code,
        "calendar": payload.get("StartCalendarInterval"),
        "conflicting_start_interval": payload.get("StartInterval"),
        "timezone": local_timezone_name(),
        "timezone_source": "system",
        "system_timezone": local_timezone_name(),
        "generated_runtime_timezone": configured_timezone_name,
        "latest_lifecycle": latest_lifecycle,
    }


def run_status(
    args: argparse.Namespace,
    runtime_env: dict[str, str],
    env: dict[str, str],
) -> int:
    result = subprocess.run(
        node_command(args, runtime_env),
        cwd=args.repo_root / "viventium_v0_4" / "LibreChat",
        env=env,
        **model_subprocess_kwargs(capture_output=True, lower_priority=False),
    )
    if result.returncode != 0:
        if result.stdout:
            sys.stdout.write(result.stdout)
        if result.stderr:
            sys.stderr.write(result.stderr)
        return int(result.returncode)
    try:
        status = json.loads(result.stdout)
    except json.JSONDecodeError:
        sys.stdout.write(result.stdout)
        return int(result.returncode)
    if not isinstance(status, dict):
        sys.stdout.write(result.stdout)
        return int(result.returncode)
    schedule_health = status.get("schedule_health")
    if not isinstance(schedule_health, dict):
        schedule_health = {}
    launch_agent = launch_agent_status(env)
    schedule_health["launch_agent"] = launch_agent
    latest = schedule_health.get("latest_scheduled_trigger")
    latest = latest if isinstance(latest, dict) else {}
    if not launch_agent["installed"] or not launch_agent["loaded"]:
        health_state = "not_loaded"
    elif schedule_health.get("missed_expected_window"):
        health_state = "missed"
    elif latest.get("status") == "failed" or (
        latest.get("exit_code") not in {None, 0}
    ):
        health_state = "failed"
    elif schedule_health.get("execution_mismatch"):
        health_state = "execution_mismatch"
    elif schedule_health.get("execution_unverified"):
        health_state = "execution_unverified"
    elif latest.get("status") == "started":
        health_state = "running"
    elif latest.get("status") == "skipped":
        health_state = "retry_pending"
    elif latest.get("status") == "success":
        health_state = "healthy"
    else:
        health_state = "awaiting_first_run"
    schedule_health["state"] = health_state
    schedule_health["healthy"] = health_state == "healthy"
    status["schedule_health"] = schedule_health
    print(json.dumps(status, indent=2))
    return int(result.returncode)


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
    env.setdefault(
        "VIVENTIUM_MEMORY_HARDENING_EFFORT",
        default_memory_hardening_effort(args, env),
    )
    if args.command == "status":
        return run_status(args, runtime_env, env)
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
