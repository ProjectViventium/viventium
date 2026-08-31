#!/usr/bin/env python3
"""Bind an installed local-QA session to the exact live service processes."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

CONTRACT_VERSION = 1
ACK_MAX_BYTES = 16 * 1024
MAX_FUTURE_SKEW_SECONDS = 60
INSTALLED_ROOT = Path(__file__).resolve().parents[2]
SERVICE_IDS = ("glasshive-runtime", "librechat-core", "telegram-bot")
REQUIRED_SERVICES = {
    "TR-026": ("librechat-core", "telegram-bot"),
    "EMO-UC-047": ("glasshive-runtime", "librechat-core"),
    "EMO-UC-048": ("librechat-core", "telegram-bot"),
    "MPV-061": ("librechat-core",),
    "PWK-UC-015": ("glasshive-runtime", "librechat-core", "telegram-bot"),
    "PWK-UC-016": ("glasshive-runtime", "librechat-core", "telegram-bot"),
    "PWK-UC-017": ("glasshive-runtime", "librechat-core", "telegram-bot"),
    "REL-UC-004": ("librechat-core",),
}
SESSION_REF = re.compile(r"^qa_[A-Za-z0-9_-]{8,64}$")
HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
PROOF = re.compile(r"^hmac-sha256:[0-9a-f]{64}$")
ACK_FIELDS = {
    "acknowledgedAt",
    "artifactIdentityDigest",
    "caseId",
    "componentArtifactDigest",
    "contractVersion",
    "installedRootHash",
    "processIdentity",
    "proof",
    "serviceId",
    "sessionRef",
}
PROCESS_FIELDS = {
    "executablePath",
    "executableSha256",
    "pid",
    "startedAt",
    "startMarker",
}


def _load_runtime_control():
    path = Path(__file__).with_name("local_qa_runtime_control.py")
    spec = importlib.util.spec_from_file_location(
        "local_qa_runtime_control_for_ack", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("local-QA runtime control is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    return module


runtime_control = _load_runtime_control()


class PrivateArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise ValueError("operation_failed")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: object) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value or ""))
    except ValueError as exc:
        raise ValueError("timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp is invalid")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _decode_token(value: object) -> bytes:
    token = str(value or "")
    try:
        decoded = base64.urlsafe_b64decode(token + "=")
    except (ValueError, TypeError) as exc:
        raise ValueError("case token is invalid") from exc
    if (
        len(decoded) != 32
        or base64.urlsafe_b64encode(decoded).decode().rstrip("=") != token
    ):
        raise ValueError("case token is invalid")
    return decoded


def _proof(payload: Mapping[str, object], token: object) -> str:
    digest = hmac.new(
        _decode_token(token),
        _canonical_json(dict(payload)).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return "hmac-sha256:" + digest


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _ps_path() -> str:
    for candidate in (Path("/bin/ps"), Path("/usr/bin/ps")):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    raise ValueError("process inspection is unavailable")


@lru_cache(maxsize=1)
def _process_inspector():
    return runtime_control._release_gate_module()


def _kernel_process_image_and_argv(pid: int) -> tuple[Path, tuple[str, ...]]:
    try:
        identity = _process_inspector()._live_process_image_and_argv(pid)
        if identity is None:
            raise ValueError("process identity is unavailable")
        executable, argv = identity
        resolved = Path(executable).resolve(strict=True)
    except (
        AttributeError,
        ImportError,
        OSError,
        RuntimeError,
        subprocess.SubprocessError,
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError("process identity is unavailable") from exc
    if (
        not isinstance(argv, tuple)
        or not argv
        or not all(isinstance(argument, str) and argument for argument in argv)
    ):
        raise ValueError("process identity is unavailable")
    return resolved, argv


def _process_cwd(pid: int) -> Path:
    proc_cwd = Path(f"/proc/{pid}/cwd")
    try:
        if proc_cwd.exists():
            return proc_cwd.resolve(strict=True)
        cwd = _process_inspector()._process_cwd(pid)
        if cwd is None:
            raise ValueError("process working directory is unavailable")
        return Path(cwd).resolve(strict=True)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("process working directory is unavailable") from exc


def _argument_is_path(argument: str, *, expected: Path, cwd: Path) -> bool:
    try:
        supplied = Path(argument)
        candidate = supplied if supplied.is_absolute() else cwd / supplied
        return candidate.resolve(strict=True) == expected.resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return False


def _script_entrypoint_index(
    argv: tuple[str, ...], *, node: bool = False
) -> int | None:
    options_with_values = (
        {
            "--conditions",
            "--env-file",
            "--env-file-if-exists",
            "--experimental-loader",
            "--import",
            "--loader",
            "--require",
            "-C",
            "-r",
        }
        if node
        else {"--check-hash-based-pycs", "-W", "-X"}
    )
    forbidden = (
        {
            "--check",
            "--eval",
            "--interactive",
            "--print",
            "--run",
            "--test",
            "-c",
            "-e",
            "-i",
            "-p",
        }
        if node
        else {"--help", "--version", "-c", "-m"}
    )
    position = 1
    while position < len(argv):
        argument = argv[position]
        if argument == "-":
            return None
        if argument == "--":
            return position + 1 if position + 1 < len(argv) else None
        if not argument.startswith("-"):
            return position
        option = argument.split("=", 1)[0]
        if (
            option in forbidden
            or (
                not node
                and not argument.startswith("--")
                and argument.startswith(("-c", "-m"))
            )
            or (
                node
                and not argument.startswith("--")
                and argument.startswith(("-e", "-p"))
            )
        ):
            return None
        position += 2 if option in options_with_values and "=" not in argument else 1
    return None


def _macos_python_framework_image(executable: Path) -> Path | None:
    if (
        sys.platform != "darwin"
        or executable.parent.name != "bin"
        or re.fullmatch(r"python(?:3(?:\.\d+)?)?", executable.name) is None
    ):
        return None
    try:
        return (
            executable.parent.parent
            / "Resources"
            / "Python.app"
            / "Contents"
            / "MacOS"
            / "Python"
        ).resolve(strict=True)
    except (OSError, RuntimeError):
        return None


def _claimed_executable_is_live(
    executable: Path,
    *,
    pid: int,
    live_image: Path,
    live_argv: tuple[str, ...],
) -> bool:
    if live_image == executable:
        return True
    if _macos_python_framework_image(executable) == live_image:
        return True
    try:
        interpreter = _process_inspector()._script_interpreter(executable)
        cwd = _process_cwd(pid)
    except (AttributeError, OSError, RuntimeError, ValueError):
        return False
    if interpreter is None:
        return False
    try:
        interpreter_path = Path(interpreter[0]).resolve(strict=True)
    except (OSError, RuntimeError):
        return False
    if (
        interpreter_path != live_image
        and _macos_python_framework_image(interpreter_path) != live_image
    ):
        return False
    position = _script_entrypoint_index(live_argv)
    return position is not None and _argument_is_path(
        live_argv[position], expected=executable, cwd=cwd
    )


def _glasshive_launch_is_valid(
    argv: tuple[str, ...], *, cwd: Path, runtime_root: Path
) -> bool:
    api_source = runtime_root / "src" / "workers_projects_runtime" / "api.py"
    wrapper = runtime_root / ".venv" / "bin" / "uvicorn"
    try:
        if cwd != runtime_root.resolve(strict=True) or not api_source.is_file():
            return False
    except (OSError, RuntimeError):
        return False

    if len(argv) >= 4 and argv[1:3] == ("-m", "uvicorn"):
        target_position = 3
    else:
        position = _script_entrypoint_index(argv)
        if position is None or not _argument_is_path(
            argv[position], expected=wrapper, cwd=cwd
        ):
            return False
        target_position = position + 1
    if target_position >= len(argv):
        return False
    target = argv[target_position]
    if target == "workers_projects_runtime.api:create_app":
        return "--factory" in argv[target_position + 1 :]
    return target == "workers_projects_runtime.api:app"


def _service_process_identity_valid(
    service_id: str, pid: int, executable_path: Path
) -> bool:
    try:
        installed_root = INSTALLED_ROOT.expanduser().resolve(strict=True)
        executable = executable_path.expanduser().resolve(strict=True)
        live_image, argv = _kernel_process_image_and_argv(pid)
        cwd = _process_cwd(pid)
        if not _claimed_executable_is_live(
            executable,
            pid=pid,
            live_image=live_image,
            live_argv=argv,
        ):
            return False
        if service_id == "glasshive-runtime":
            return _glasshive_launch_is_valid(
                argv,
                cwd=cwd,
                runtime_root=installed_root
                / "viventium_v0_4"
                / "GlassHive"
                / "runtime_phase1",
            )
        if service_id == "librechat-core":
            expected = (
                installed_root
                / "viventium_v0_4"
                / "LibreChat"
                / "api"
                / "server"
                / "index.js"
            )
            position = _script_entrypoint_index(argv, node=True)
        elif service_id == "telegram-bot":
            expected = (
                installed_root
                / "viventium_v0_4"
                / "telegram-viventium"
                / "TelegramVivBot"
                / "bot.py"
            )
            position = _script_entrypoint_index(argv)
        else:
            return False
        return position is not None and _argument_is_path(
            argv[position], expected=expected, cwd=cwd
        )
    except (
        AttributeError,
        ImportError,
        OSError,
        RuntimeError,
        subprocess.SubprocessError,
        TypeError,
        ValueError,
    ):
        return False


def _process_started_at(raw: str) -> datetime:
    try:
        local_timezone = datetime.now().astimezone().tzinfo
        local = datetime.strptime(
            " ".join(raw.split()), "%a %b %d %H:%M:%S %Y"
        ).replace(tzinfo=local_timezone)
        return local.astimezone(timezone.utc)
    except ValueError as exc:
        raise ValueError("process identity is invalid") from exc


def probe_process(pid: int, executable_path: Path) -> dict[str, object]:
    if type(pid) is not int or pid < 2:
        raise ValueError("process identity is invalid")
    executable = executable_path.expanduser().resolve(strict=True)
    metadata = executable.stat()
    if not stat.S_ISREG(metadata.st_mode) or not os.access(executable, os.X_OK):
        raise ValueError("process executable is invalid")
    live_image, live_argv = _kernel_process_image_and_argv(pid)
    if not _claimed_executable_is_live(
        executable,
        pid=pid,
        live_image=live_image,
        live_argv=live_argv,
    ):
        raise ValueError("process executable does not match the live process")
    result = subprocess.run(
        [_ps_path(), "-p", str(pid), "-o", "uid=", "-o", "lstart="],
        text=True,
        capture_output=True,
        timeout=3,
        check=False,
    )
    rows = result.stdout.splitlines()
    fields = rows[0].split(maxsplit=1) if len(rows) == 1 else []
    if (
        result.returncode != 0
        or len(fields) != 2
        or not fields[0].isdecimal()
        or int(fields[0]) != os.geteuid()
    ):
        raise ValueError("process identity is invalid")
    raw_start = " ".join(fields[1].split())
    started = _process_started_at(raw_start)
    if _kernel_process_image_and_argv(pid) != (live_image, live_argv):
        raise ValueError("process identity changed during verification")
    marker = hashlib.sha256(f"{pid}\0{raw_start}".encode()).hexdigest()
    return {
        "pid": pid,
        "startedAt": _iso(started),
        "startMarker": "sha256:" + marker,
        "executablePath": str(executable),
        "executableSha256": _sha256_file(executable),
    }


def _state_times_valid(state_payload: Mapping[str, object], now: datetime) -> bool:
    try:
        started = _parse_time(state_payload.get("startedAt"))
        expires = _parse_time(state_payload.get("expiresAt"))
    except ValueError:
        return False
    return started <= now < expires


def _process_after_activation(
    process_identity: Mapping[str, object], state_payload: Mapping[str, object]
) -> bool:
    try:
        process_started = _parse_time(process_identity.get("startedAt"))
        session_started = _parse_time(state_payload.get("startedAt"))
    except ValueError:
        return False
    return process_started.replace(microsecond=0) >= session_started.replace(
        microsecond=0
    )


def _ack_path(ack_root: Path, session_ref: str, service_id: str) -> Path:
    if not SESSION_REF.fullmatch(session_ref) or service_id not in SERVICE_IDS:
        raise ValueError("acknowledgement target is invalid")
    supplied_root = ack_root.expanduser().resolve(strict=False)
    if supplied_root.is_symlink():
        raise ValueError("acknowledgement target is invalid")
    return supplied_root / session_ref / f"{service_id}.json"


def _required_services(case_id: str) -> tuple[str, ...]:
    required = REQUIRED_SERVICES.get(case_id)
    if required is None:
        raise ValueError("local-QA case is unsupported")
    if (
        not isinstance(required, tuple)
        or not required
        or any(service_id not in SERVICE_IDS for service_id in required)
        or len(set(required)) != len(required)
    ):
        raise ValueError("local-QA required service identities are invalid")
    return required


def acknowledge(
    *,
    state_payload: Mapping[str, object],
    ack_root: Path,
    service_id: str,
    pid: int,
    executable_path: Path,
    parent_pid: int | None = None,
    process_probe: Callable[[int, Path], dict[str, object]] = probe_process,
    now: datetime | None = None,
) -> dict[str, object]:
    checked_at = (now or _utc_now()).astimezone(timezone.utc)
    case_id = str(state_payload.get("caseId") or "")
    required = _required_services(case_id)
    if service_id not in required:
        return {"acknowledged": False, "serviceId": service_id}
    if pid != (os.getppid() if parent_pid is None else parent_pid):
        raise ValueError("service process identity did not match the caller")
    if not _state_times_valid(state_payload, checked_at):
        raise ValueError("local-QA session is not active")
    process_identity = process_probe(pid, executable_path)
    if set(process_identity) != PROCESS_FIELDS or not _process_after_activation(
        process_identity, state_payload
    ):
        raise ValueError("service process predates the local-QA session")
    if not _service_process_identity_valid(service_id, pid, executable_path):
        raise ValueError("service process identity does not match its installed launch")
    session_ref = str(state_payload.get("sessionRef") or "")
    unsigned: dict[str, object] = {
        "acknowledgedAt": _iso(checked_at),
        "artifactIdentityDigest": state_payload.get("artifactIdentityDigest"),
        "caseId": case_id,
        "componentArtifactDigest": state_payload.get("componentArtifactDigest"),
        "contractVersion": CONTRACT_VERSION,
        "installedRootHash": state_payload.get("installedRootHash"),
        "processIdentity": process_identity,
        "serviceId": service_id,
        "sessionRef": session_ref,
    }
    payload = {**unsigned, "proof": _proof(unsigned, state_payload.get("caseToken"))}
    target = _ack_path(ack_root, session_ref, service_id)
    runtime_control._write_private_json(target, payload)
    return {"acknowledged": True, "serviceId": service_id}


def _ack_shape_valid(ack: object) -> bool:
    if not isinstance(ack, dict) or set(ack) != ACK_FIELDS:
        return False
    process = ack.get("processIdentity")
    return bool(
        ack.get("contractVersion") == CONTRACT_VERSION
        and ack.get("serviceId") in SERVICE_IDS
        and SESSION_REF.fullmatch(str(ack.get("sessionRef") or ""))
        and all(
            HASH.fullmatch(str(ack.get(field) or ""))
            for field in (
                "artifactIdentityDigest",
                "componentArtifactDigest",
                "installedRootHash",
            )
        )
        and PROOF.fullmatch(str(ack.get("proof") or ""))
        and isinstance(process, dict)
        and set(process) == PROCESS_FIELDS
        and isinstance(process.get("pid"), int)
        and process.get("pid") >= 2
        and all(
            HASH.fullmatch(str(process.get(field) or ""))
            for field in ("startMarker", "executableSha256")
        )
        and Path(str(process.get("executablePath") or "")).is_absolute()
    )


def acknowledgement_valid(
    ack: object,
    *,
    state_payload: Mapping[str, object],
    expected_service_id: str | None = None,
    process_probe: Callable[[int, Path], dict[str, object]] = probe_process,
    now: datetime | None = None,
) -> bool:
    checked_at = (now or _utc_now()).astimezone(timezone.utc)
    if not _ack_shape_valid(ack) or not _state_times_valid(state_payload, checked_at):
        return False
    assert isinstance(ack, dict)
    try:
        required = _required_services(str(state_payload.get("caseId") or ""))
    except ValueError:
        return False
    if ack.get("serviceId") not in required or (
        expected_service_id is not None and ack.get("serviceId") != expected_service_id
    ):
        return False
    expected = {
        "artifactIdentityDigest": state_payload.get("artifactIdentityDigest"),
        "caseId": state_payload.get("caseId"),
        "componentArtifactDigest": state_payload.get("componentArtifactDigest"),
        "installedRootHash": state_payload.get("installedRootHash"),
        "sessionRef": state_payload.get("sessionRef"),
    }
    if any(ack.get(field) != value for field, value in expected.items()):
        return False
    try:
        acknowledged = _parse_time(ack.get("acknowledgedAt"))
        started = _parse_time(state_payload.get("startedAt"))
        expires = _parse_time(state_payload.get("expiresAt"))
    except ValueError:
        return False
    if not (
        started <= acknowledged < expires
        and acknowledged <= checked_at + timedelta(seconds=MAX_FUTURE_SKEW_SECONDS)
    ):
        return False
    unsigned = {key: value for key, value in ack.items() if key != "proof"}
    try:
        expected_proof = _proof(unsigned, state_payload.get("caseToken"))
    except ValueError:
        return False
    if not hmac.compare_digest(str(ack.get("proof")), expected_proof):
        return False
    process = ack["processIdentity"]
    try:
        current = process_probe(
            int(process["pid"]), Path(str(process["executablePath"]))
        )
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError):
        return False
    return (
        current == process
        and _process_after_activation(process, state_payload)
        and _service_process_identity_valid(
            str(ack["serviceId"]),
            int(process["pid"]),
            Path(str(process["executablePath"])),
        )
    )


def _read_ack(path: Path) -> object:
    try:
        _raw, payload = runtime_control._read_private_json(
            path,
            label="local-QA service acknowledgement",
            max_bytes=ACK_MAX_BYTES,
        )
        return payload
    except (OSError, RuntimeError, ValueError):
        return None


def restart_status(
    state_payload: Mapping[str, object],
    *,
    ack_root: Path,
    process_probe: Callable[[int, Path], dict[str, object]] = probe_process,
    now: datetime | None = None,
) -> dict[str, object]:
    case_id = str(state_payload.get("caseId") or "")
    required = _required_services(case_id)
    valid: list[tuple[str, dict[str, object]]] = []
    acknowledged_service_ids: set[str] = set()
    acknowledged_pids: set[int] = set()
    acknowledged_start_markers: set[str] = set()
    session_ref = str(state_payload.get("sessionRef") or "")
    for service_id in required:
        payload = _read_ack(_ack_path(ack_root, session_ref, service_id))
        if acknowledgement_valid(
            payload,
            state_payload=state_payload,
            expected_service_id=service_id,
            process_probe=process_probe,
            now=now,
        ):
            assert isinstance(payload, dict)
            identity = payload["processIdentity"]
            assert isinstance(identity, dict)
            live_pid = int(identity["pid"])
            start_marker = str(identity["startMarker"])
            if (
                service_id in acknowledged_service_ids
                or live_pid in acknowledged_pids
                or start_marker in acknowledged_start_markers
            ):
                continue
            acknowledged_service_ids.add(service_id)
            acknowledged_pids.add(live_pid)
            acknowledged_start_markers.add(start_marker)
            valid.append((service_id, payload))
    acknowledged = [service_id for service_id, _payload in valid]
    missing = [service_id for service_id in required if service_id not in acknowledged]
    digest = ""
    if not missing:
        digest = (
            "sha256:"
            + hashlib.sha256(
                _canonical_json([payload for _service, payload in valid]).encode(
                    "utf-8"
                )
            ).hexdigest()
        )
    return {
        "caseId": case_id,
        "restartState": "ready" if not missing else "waiting",
        "requiredServices": list(required),
        "acknowledgedServices": acknowledged,
        "missingServices": missing,
        "serviceAckDigest": digest,
        "sessionRef": session_ref,
    }


def clear_acknowledgements(ack_root: Path, session_ref: str) -> None:
    target = _ack_path(ack_root, session_ref, SERVICE_IDS[0]).parent
    if not target.exists():
        return
    if target.is_symlink() or not target.is_dir():
        raise ValueError("acknowledgement target is invalid")
    for child in target.iterdir():
        if (
            child.is_symlink()
            or not child.is_file()
            or child.name not in {f"{service_id}.json" for service_id in SERVICE_IDS}
        ):
            raise ValueError("acknowledgement target is invalid")
        child.unlink()
    target.rmdir()


def _environment_paths(environ: Mapping[str, str]) -> dict[str, Path]:
    app_support_value = str(environ.get("VIVENTIUM_APP_SUPPORT_DIR") or "")
    app_support = Path(app_support_value).expanduser()
    if not app_support_value or not app_support.is_absolute():
        raise ValueError("local-QA environment is invalid")
    app_support = app_support.resolve(strict=True)
    installed_root = Path(__file__).resolve(strict=True).parents[2]
    runtime_dir = app_support / "runtime"
    values = {
        "state": runtime_dir / "local-qa" / "active.json",
        "installed_root": installed_root,
        "artifact_identity": runtime_dir / "parallel-work-artifact-identity.json",
        "local_qa_request": runtime_dir / "parallel-work-local-qa-request.json",
        "ack_root": runtime_dir / "local-qa" / "acks",
    }
    for name in ("state", "installed_root", "artifact_identity", "local_qa_request"):
        values[name] = values[name].resolve(strict=True)
    return values


def acknowledge_from_environment(
    *,
    service_id: str,
    pid: int,
    executable_path: Path,
    environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    environment = os.environ if environ is None else environ
    paths = _environment_paths(environment)
    state = runtime_control.active_session(
        state_path=paths["state"],
        installed_root=paths["installed_root"],
        artifact_identity_path=paths["artifact_identity"],
        local_qa_request_path=paths["local_qa_request"],
    )
    if not (
        hmac.compare_digest(
            str(environment.get("VIVENTIUM_LOCAL_QA_CASE_TOKEN") or ""),
            str(state.get("caseToken") or ""),
        )
        and environment.get("VIVENTIUM_LOCAL_QA_CASE_ID") == state.get("caseId")
        and environment.get("VIVENTIUM_LOCAL_QA_SESSION_REF") == state.get("sessionRef")
    ):
        raise ValueError("local-QA environment is invalid")
    return acknowledge(
        state_payload=state,
        ack_root=paths["ack_root"],
        service_id=service_id,
        pid=pid,
        executable_path=executable_path,
    )


def _reject_duplicate_options(argv: Iterable[str]) -> None:
    seen: set[str] = set()
    for value in argv:
        if not value.startswith("--"):
            continue
        option = value.split("=", 1)[0]
        if option in seen:
            raise ValueError("operation_failed")
        seen.add(option)


def main(argv: Iterable[str] | None = None) -> int:
    parser = PrivateArgumentParser(description=__doc__, allow_abbrev=False)
    subcommands = parser.add_subparsers(dest="command", required=True)
    acknowledge_command = subcommands.add_parser("acknowledge", allow_abbrev=False)
    acknowledge_command.add_argument("--service-id", choices=SERVICE_IDS, required=True)
    acknowledge_command.add_argument("--pid", type=int, required=True)
    acknowledge_command.add_argument("--executable", type=Path, required=True)
    values = list(argv) if argv is not None else sys.argv[1:]
    try:
        _reject_duplicate_options(values)
        args = parser.parse_args(values)
        result = acknowledge_from_environment(
            service_id=args.service_id,
            pid=args.pid,
            executable_path=args.executable,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (
        OSError,
        RuntimeError,
        subprocess.SubprocessError,
        UnicodeError,
        ValueError,
    ):
        print(json.dumps({"error": "operation_failed"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
