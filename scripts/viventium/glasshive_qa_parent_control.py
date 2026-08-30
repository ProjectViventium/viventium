#!/usr/bin/env python3
"""Own exact installed GlassHive local-QA fixtures and deterministic controls."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import importlib.util
import json
import os
import re
import secrets
import selectors
import shlex
import signal
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Callable, Iterable, Mapping, Sequence


CONTRACT_VERSION = 1
CASE_BOUNDARIES = {
    "PWK-UC-016": (
        "provider_auth_missing",
        "provider_quota_cooldown_fallback",
        "provider_unavailable",
        "provider_internal_retry_threshold",
        "declared_long_fresh_then_stale",
        "maximum_capacity_overflow",
        "measured_memory_4_3_gib_vs_5_gib",
        "last_reservation_competition",
        "low_disk",
    ),
    "PWK-UC-017": (
        "callback_transport_interruption",
        "claimed_queue_stall",
        "admitted_queue_stall",
        "status_refresh_timeout_race",
        "expired_sender_lease_race",
        "duplicate_callback_replay",
        "artifact_link_expired",
        "artifact_unavailable_restart_recovery",
    ),
}
CASE_MODES = {
    "PWK-UC-016": "pwk_uc_016",
    "PWK-UC-017": "pwk_uc_017",
}
RUN_SCOPED_BOUNDARIES = frozenset(
    boundary
    for boundaries in CASE_BOUNDARIES.values()
    for boundary in boundaries
)
ARTIFACT_SCOPED_BOUNDARIES = frozenset(
    {"artifact_link_expired", "artifact_unavailable_restart_recovery"}
)
HASH_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")
CONTROL_REF_PATTERN = re.compile(r"^qac_sha256:[a-f0-9]{64}$")
NAMESPACE_PATTERN = re.compile(r"^[a-f0-9]{32}$")
ID_PATTERN = re.compile(r"^[A-Za-z0-9_:-]{8,160}$")
PRIVATE_INPUT_MAX_BYTES = 16 * 1024
OWNER_SCOPE_MAX_BYTES = 8 * 1024
PARENT_STATE_MAX_BYTES = 24 * 1024
RUNTIME_ENV_MAX_BYTES = 64 * 1024
CHILD_OUTPUT_MAX_BYTES = 64 * 1024
CHILD_ERROR_MAX_BYTES = 16 * 1024
PARENT_STATE_FIELDS = frozenset(
    {
        "artifactId",
        "artifactIdentityDigest",
        "caseId",
        "componentArtifactDigest",
        "contractVersion",
        "controlArtifactDigest",
        "createdAt",
        "expiresAt",
        "fixtureRef",
        "idempotencyKey",
        "installedRootHash",
        "namespace",
        "originRef",
        "ownerId",
        "projectId",
        "requestDigest",
        "runId",
        "sessionRef",
        "status",
        "workId",
        "workerId",
    }
)
PATH_ENV = {
    "parent_state_path": "VIVENTIUM_GLASSHIVE_QA_PARENT_STATE",
    "session_state_path": "VIVENTIUM_GLASSHIVE_QA_SESSION_STATE",
    "installed_root": "VIVENTIUM_GLASSHIVE_QA_INSTALLED_ROOT",
    "artifact_identity_path": "VIVENTIUM_GLASSHIVE_QA_ARTIFACT_IDENTITY",
    "local_qa_request_path": "VIVENTIUM_GLASSHIVE_QA_LOCAL_REQUEST",
    "runtime_env_path": "VIVENTIUM_GLASSHIVE_QA_RUNTIME_ENV",
}
LIBRECHAT_ENV_PATH_ENV = "VIVENTIUM_GLASSHIVE_QA_LIBRECHAT_ENV"
OWNER_SCOPE_FIELDS = frozenset(
    {
        "attestation",
        "caseId",
        "contractVersion",
        "expiresAtMs",
        "issuedAtMs",
        "nonce",
        "ownerEmail",
        "ownerId",
        "ownerRole",
        "sessionRef",
    }
)


class ParentControlError(RuntimeError):
    """Reject unsafe parent-control work without exposing private values."""


class DuplicateJsonKeyError(ValueError):
    pass


class PrivateArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise ParentControlError("operation_failed")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError("duplicate JSON key")
        result[key] = value
    return result


def _loads_strict_json(raw: str) -> object:
    return json.loads(raw, object_pairs_hook=_unique_object)


def _reject_duplicate_options(argv: Iterable[str]) -> None:
    seen: set[str] = set()
    for argument in argv:
        if not argument.startswith("--"):
            continue
        option = argument.split("=", 1)[0]
        if option in seen:
            raise ParentControlError("operation_failed")
        seen.add(option)


def _load_path(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ParentControlError("operation_failed")
    module = importlib.util.module_from_spec(spec)
    try:
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    except Exception as exc:
        raise ParentControlError("operation_failed") from exc
    return module


def _session_module() -> ModuleType:
    return _load_path(
        Path(__file__).with_name("local_qa_runtime_control.py"),
        "viventium_local_qa_runtime_for_glasshive_parent",
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: object) -> datetime:
    raw = str(value or "")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ParentControlError("operation_failed") from exc
    if parsed.tzinfo is None or raw != _iso(parsed):
        raise ParentControlError("operation_failed")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def _sha256(domain: str, value: str) -> str:
    digest = hashlib.sha256(f"glasshive-parent-v1\0{domain}\0{value}".encode()).hexdigest()
    return f"sha256:{digest}"


def _nested_scope_hash(domain: str, value: str) -> str:
    digest = hashlib.sha256(
        f"glasshive-local-qa-v1\0{domain}\0{value}".encode()
    ).hexdigest()
    return f"sha256:{digest}"


def _selected_owner_scope_attestation(
    payload: Mapping[str, object], signing_secret: str
) -> str:
    canonical = json.dumps(
        {key: payload[key] for key in sorted(OWNER_SCOPE_FIELDS - {"attestation"})},
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hmac.new(
        signing_secret.encode("utf-8"),
        ("glasshive-selected-owner-scope-v1\0" + canonical).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _verify_selected_owner_scope(
    payload: Mapping[str, object],
    *,
    session: Mapping[str, object],
    signing_secret: str,
    now: datetime | None = None,
) -> dict[str, str]:
    if not isinstance(payload, Mapping) or set(payload) != OWNER_SCOPE_FIELDS:
        raise ParentControlError("operation_failed")
    checked_at = (now or _utc_now()).astimezone(timezone.utc)
    checked_ms = int(checked_at.timestamp() * 1000)
    issued_at_ms = payload.get("issuedAtMs")
    expires_at_ms = payload.get("expiresAtMs")
    owner_id = str(payload.get("ownerId") or "").strip()
    owner_email = str(payload.get("ownerEmail") or "").strip().lower()
    owner_role = str(payload.get("ownerRole") or "").strip().upper()
    nonce = str(payload.get("nonce") or "")
    parts = owner_email.split("@")
    if (
        payload.get("contractVersion") != CONTRACT_VERSION
        or payload.get("caseId") != session.get("caseId")
        or payload.get("sessionRef") != session.get("sessionRef")
        or not ID_PATTERN.fullmatch(owner_id)
        or len(parts) != 2
        or not parts[0]
        or parts[1] not in {"example.com", "viventium.local", "localhost"}
        or owner_role != "USER"
        or not re.fullmatch(r"[a-f0-9]{32}", nonce)
        or isinstance(issued_at_ms, bool)
        or not isinstance(issued_at_ms, int)
        or isinstance(expires_at_ms, bool)
        or not isinstance(expires_at_ms, int)
        or issued_at_ms > checked_ms + 5_000
        or checked_ms - issued_at_ms > 30_000
        or expires_at_ms != issued_at_ms + 30_000
        or expires_at_ms < checked_ms
        or expires_at_ms > int(_parse_time(session.get("expiresAt")).timestamp() * 1000)
        or not signing_secret
        or not hmac.compare_digest(
            str(payload.get("attestation") or ""),
            _selected_owner_scope_attestation(payload, signing_secret),
        )
    ):
        raise ParentControlError("operation_failed")
    return {
        "ownerEmail": owner_email,
        "ownerId": owner_id,
        "ownerRole": owner_role,
    }


def _read_selected_owner_scope_stdin() -> dict[str, object]:
    if sys.stdin.isatty():
        raise ParentControlError("operation_failed")
    try:
        raw = sys.stdin.buffer.read(OWNER_SCOPE_MAX_BYTES + 1)
        if not raw or len(raw) > OWNER_SCOPE_MAX_BYTES:
            raise ParentControlError("operation_failed")
        payload = _loads_strict_json(raw.decode("utf-8", errors="strict"))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise ParentControlError("operation_failed") from exc
    if not isinstance(payload, dict):
        raise ParentControlError("operation_failed")
    return payload


def _root_hash(path: Path) -> str:
    return _session_module()._root_hash(path)


def _runtime_root(installed_root: Path) -> Path:
    try:
        root = installed_root.expanduser().resolve(strict=True)
        runtime = root / "viventium_v0_4" / "GlassHive" / "runtime_phase1"
        module = runtime / "src" / "workers_projects_runtime" / "local_qa_control.py"
        if not runtime.is_dir() or not module.is_file():
            raise ParentControlError("operation_failed")
        return runtime.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ParentControlError("operation_failed") from exc


def _control_artifact_digest(installed_root: Path) -> str:
    package = _runtime_root(installed_root) / "src" / "workers_projects_runtime"
    digest = hashlib.sha256()
    try:
        sources = sorted(package.glob("*.py"), key=lambda item: item.name)
        if not sources:
            raise ParentControlError("operation_failed")
        for source in sources:
            digest.update(source.name.encode("utf-8"))
            digest.update(b"\0")
            digest.update(source.read_bytes())
            digest.update(b"\0")
    except OSError as exc:
        raise ParentControlError("operation_failed") from exc
    return "sha256:" + digest.hexdigest()


def _read_private_json(path: Path, *, label: str, max_bytes: int) -> dict[str, object]:
    try:
        raw = _session_module()._read_private_file(path, label=label, max_bytes=max_bytes)
        payload = _loads_strict_json(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, ValueError, json.JSONDecodeError, DuplicateJsonKeyError) as exc:
        raise ParentControlError("operation_failed") from exc
    if not isinstance(payload, dict):
        raise ParentControlError("operation_failed")
    return payload


def _write_private_json(path: Path, payload: dict[str, object]) -> None:
    try:
        if path.exists() or path.is_symlink():
            metadata = path.lstat()
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) != 0o600
                or metadata.st_nlink != 1
            ):
                raise ParentControlError("operation_failed")
        _session_module()._write_private_json(path, payload)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ParentControlError("operation_failed") from exc


def _raw_session(state_path: Path) -> dict[str, object]:
    try:
        return _session_module()._read_state(state_path)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ParentControlError("operation_failed") from exc


def _active_session(
    *,
    session_state_path: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    local_qa_request_path: Path,
    now: datetime | None = None,
) -> dict[str, object]:
    try:
        return _session_module().active_session(
            state_path=session_state_path,
            installed_root=installed_root,
            artifact_identity_path=artifact_identity_path,
            local_qa_request_path=local_qa_request_path,
            now=now,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        raise ParentControlError("operation_failed") from exc


def _parse_runtime_env(path: Path) -> dict[str, str]:
    try:
        raw = _session_module()._read_private_file(
            path,
            label="configured GlassHive environment",
            max_bytes=RUNTIME_ENV_MAX_BYTES,
        )
        lines = raw.decode("utf-8", errors="strict").splitlines()
    except (OSError, UnicodeError, ValueError) as exc:
        raise ParentControlError("operation_failed") from exc
    result: dict[str, str] = {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.removeprefix("export ")
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or key in result:
            raise ParentControlError("operation_failed")
        try:
            parts = shlex.split(raw_value, comments=False, posix=True)
        except ValueError as exc:
            raise ParentControlError("operation_failed") from exc
        result[key] = parts[0] if len(parts) == 1 else raw_value.strip("'\"")
    return result


def _database_path(raw: str) -> Path:
    exact, _identity = _database_path_identity(raw)
    return exact


def _database_path_identity(
    raw: str,
) -> tuple[Path, tuple[tuple[int, ...], tuple[tuple[int, ...], ...]]]:
    descriptor = directory_descriptor = -1
    try:
        supplied = Path(raw).expanduser()
        if (
            not supplied.is_absolute()
            or supplied.name in {"", ".", ".."}
            or any(part in {"", ".", ".."} for part in supplied.parts[1:])
        ):
            raise ParentControlError("operation_failed")
        session_module = _session_module()
        descriptor, directory_descriptor, parents = session_module._open_private_path(
            supplied,
            label="GlassHive runtime database",
            max_bytes=(1 << 63) - 1,
            min_bytes=0,
        )
        metadata = os.fstat(descriptor)
        current = os.stat(
            supplied.name, dir_fd=directory_descriptor, follow_symlinks=False
        )
        file_identity = session_module._file_identity(metadata)
        if file_identity != session_module._file_identity(current):
            raise ParentControlError("operation_failed")
    except (OSError, RuntimeError, ValueError) as exc:
        raise ParentControlError("operation_failed") from exc
    finally:
        for opened in (descriptor, directory_descriptor):
            if opened >= 0:
                try:
                    os.close(opened)
                except OSError:
                    pass
    stable_parents = tuple(identity[:5] for identity in parents)
    return supplied, (file_identity[:6], stable_parents)


def _assert_database_path_identity(
    path: Path,
    expected: tuple[tuple[int, ...], tuple[tuple[int, ...], ...]],
) -> None:
    current_path, current = _database_path_identity(str(path))
    if current_path != path or current != expected:
        raise ParentControlError("operation_failed")


def _cleanup_source_snapshots(
    *,
    parent_state_path: Path,
    session_state_path: Path,
    artifact_identity_path: Path,
    local_qa_request_path: Path,
    runtime_env_path: Path,
) -> tuple[ModuleType, dict[str, tuple[Path, str, int, object]]]:
    session_module = _session_module()
    definitions = {
        "parent": (
            parent_state_path,
            "GlassHive fixture state",
            PARENT_STATE_MAX_BYTES,
        ),
        "session": (
            session_state_path,
            "local-QA session state",
            session_module.SESSION_STATE_MAX_BYTES,
        ),
        "artifact": (
            artifact_identity_path,
            "installed artifact identity",
            session_module.ARTIFACT_IDENTITY_MAX_BYTES,
        ),
        "request": (
            local_qa_request_path,
            "explicit local-QA request",
            session_module.REQUEST_MAX_BYTES,
        ),
        "runtime": (
            runtime_env_path,
            "configured GlassHive environment",
            RUNTIME_ENV_MAX_BYTES,
        ),
    }
    snapshots: dict[str, tuple[Path, str, int, object]] = {}
    try:
        for name, (path, label, max_bytes) in definitions.items():
            snapshots[name] = (
                path,
                label,
                max_bytes,
                session_module._read_private_file_snapshot(
                    path, label=label, max_bytes=max_bytes
                ),
            )
    except (OSError, RuntimeError, ValueError) as exc:
        raise ParentControlError("operation_failed") from exc
    return session_module, snapshots


def _assert_cleanup_sources(
    session_module: ModuleType,
    snapshots: Mapping[str, tuple[Path, str, int, object]],
) -> None:
    try:
        for path, label, max_bytes, snapshot in snapshots.values():
            session_module._assert_private_file_snapshot(
                path, snapshot, label=label, max_bytes=max_bytes
            )
    except (OSError, RuntimeError, ValueError) as exc:
        raise ParentControlError("operation_failed") from exc


def _runtime_authority(
    runtime_env_path: Path, session: Mapping[str, object]
) -> tuple[dict[str, str], Path]:
    authority, db_path, _identity = _runtime_authority_bound(runtime_env_path, session)
    return authority, db_path


def _runtime_authority_bound(
    runtime_env_path: Path, session: Mapping[str, object]
) -> tuple[
    dict[str, str],
    Path,
    tuple[tuple[int, ...], tuple[tuple[int, ...], ...]],
]:
    values = _parse_runtime_env(runtime_env_path)
    runtime_expected = {
        "VIVENTIUM_GLASSHIVE_LOCAL_QA_MODE": str(session["mode"]),
        "VIVENTIUM_LOCAL_QA_CASE_ID": str(session["caseId"]),
        "VIVENTIUM_LOCAL_QA_CASE_TOKEN": str(session["caseToken"]),
        "VIVENTIUM_LOCAL_QA_SESSION_REF": str(session["sessionRef"]),
        "VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST": str(
            session["componentArtifactDigest"]
        ),
    }
    candidate_digest = str(session.get("artifactIdentityDigest") or "")
    component_digest = str(session.get("componentArtifactDigest") or "")
    if (
        not HASH_PATTERN.fullmatch(candidate_digest)
        or not HASH_PATTERN.fullmatch(component_digest)
        or any(values.get(key) != value for key, value in runtime_expected.items())
    ):
        raise ParentControlError("operation_failed")
    db_path, database_identity = _database_path_identity(
        str(values.get("WPR_DB_PATH") or "")
    )
    return {
        **runtime_expected,
        "VIVENTIUM_LOCAL_QA_CANDIDATE_DIGEST": candidate_digest,
    }, db_path, database_identity


def _clean_child_environment(
    *, runtime_root: Path, repository_root: Path, db_path: Path
) -> dict[str, str]:
    environment: dict[str, str] = {}
    for key in ("LANG", "LC_ALL", "LC_CTYPE", "PATH", "TMPDIR"):
        value = str(os.environ.get(key, "") or "").strip()
        if value:
            environment[key] = value
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(runtime_root / "src"), str(repository_root))
    )
    environment["WPR_DB_PATH"] = str(db_path)
    return environment


def _python_binary() -> str:
    try:
        exact = Path(sys.executable).resolve(strict=True)
        metadata = exact.stat()
    except (OSError, RuntimeError) as exc:
        raise ParentControlError("operation_failed") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid not in {0, os.getuid()}
        or stat.S_IMODE(metadata.st_mode) & 0o022
        or not os.access(exact, os.X_OK)
    ):
        raise ParentControlError("operation_failed")
    return str(exact)


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=1)
    except (OSError, ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass


def _run_private_json(
    *,
    argv: Sequence[str],
    cwd: Path,
    env: Mapping[str, str],
    document: Mapping[str, object],
    private_values: Sequence[str],
    receipt: bool = False,
) -> tuple[dict[str, object], dict[str, object] | None]:
    encoded_private = [value.encode() for value in private_values if value]
    joined_argv = "\0".join(str(value) for value in argv).encode()
    if any(value in joined_argv for value in encoded_private):
        raise ParentControlError("operation_failed")
    input_file = tempfile.NamedTemporaryFile(mode="w+b", delete=False)
    input_path = Path(input_file.name)
    receipt_file = tempfile.TemporaryFile(mode="w+b") if receipt else None
    try:
        os.fchmod(input_file.fileno(), 0o600)
        raw_document = json.dumps(
            dict(document), sort_keys=True, separators=(",", ":")
        ).encode()
        if len(raw_document) > PRIVATE_INPUT_MAX_BYTES:
            raise ParentControlError("operation_failed")
        input_file.write(raw_document)
        input_file.flush()
        input_file.seek(0)
        child_argv = [*argv, "--input-fd", str(input_file.fileno())]
        pass_fds = [input_file.fileno()]
        if receipt_file is not None:
            os.fchmod(receipt_file.fileno(), 0o600)
            child_argv.extend(("--receipt-fd", str(receipt_file.fileno())))
            pass_fds.append(receipt_file.fileno())
        process = subprocess.Popen(
            child_argv,
            cwd=cwd,
            env=dict(env),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            pass_fds=tuple(pass_fds),
            start_new_session=True,
        )
        selector = selectors.DefaultSelector()
        assert process.stdout is not None and process.stderr is not None
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        output = bytearray()
        error = bytearray()
        try:
            while selector.get_map():
                events = selector.select(timeout=30)
                if not events:
                    _terminate_process(process)
                    raise ParentControlError("operation_failed")
                for key, _mask in events:
                    chunk = os.read(key.fileobj.fileno(), 8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    target = output if key.data == "stdout" else error
                    target.extend(chunk)
                    limit = (
                        CHILD_OUTPUT_MAX_BYTES
                        if key.data == "stdout"
                        else CHILD_ERROR_MAX_BYTES
                    )
                    if len(target) > limit:
                        _terminate_process(process)
                        raise ParentControlError("operation_failed")
            return_code = process.wait(timeout=2)
        except subprocess.TimeoutExpired as exc:
            _terminate_process(process)
            raise ParentControlError("operation_failed") from exc
        finally:
            selector.close()
        combined = bytes(output) + bytes(error)
        if any(value in combined for value in encoded_private):
            raise ParentControlError("operation_failed")
        if return_code != 0 or error.strip():
            raise ParentControlError("operation_failed")
        try:
            public = _loads_strict_json(output.decode("utf-8", errors="strict"))
        except (UnicodeError, json.JSONDecodeError, DuplicateJsonKeyError) as exc:
            raise ParentControlError("operation_failed") from exc
        if not isinstance(public, dict):
            raise ParentControlError("operation_failed")
        private: dict[str, object] | None = None
        if receipt_file is not None:
            receipt_file.seek(0)
            raw_receipt = receipt_file.read(PRIVATE_INPUT_MAX_BYTES + 1)
            if len(raw_receipt) > PRIVATE_INPUT_MAX_BYTES:
                raise ParentControlError("operation_failed")
            try:
                parsed = _loads_strict_json(raw_receipt.decode("utf-8", errors="strict"))
            except (UnicodeError, json.JSONDecodeError, DuplicateJsonKeyError) as exc:
                raise ParentControlError("operation_failed") from exc
            if not isinstance(parsed, dict):
                raise ParentControlError("operation_failed")
            private = parsed
        return public, private
    finally:
        input_file.close()
        input_path.unlink(missing_ok=True)
        if receipt_file is not None:
            receipt_file.close()


def _state(path: Path) -> dict[str, object]:
    state = _read_private_json(
        path, label="GlassHive fixture state", max_bytes=PARENT_STATE_MAX_BYTES
    )
    if set(state) != set(PARENT_STATE_FIELDS) or state.get("contractVersion") != 1:
        raise ParentControlError("operation_failed")
    case_id = str(state.get("caseId") or "")
    status_value = str(state.get("status") or "")
    ids = [
        str(state.get(name) or "")
        for name in ("ownerId", "idempotencyKey", "originRef", "artifactId")
    ]
    ready_ids = [
        str(state.get(name) or "")
        for name in ("projectId", "workerId", "workId", "runId")
    ]
    if (
        case_id not in CASE_BOUNDARIES
        or status_value not in {"provisioning", "ready"}
        or not NAMESPACE_PATTERN.fullmatch(str(state.get("namespace") or ""))
        or not all(ID_PATTERN.fullmatch(value) for value in ids[:3])
        or not str(state.get("artifactId") or "").startswith("artifact_sha256:")
        or not all(
            HASH_PATTERN.fullmatch(str(state.get(name) or ""))
            for name in (
                "artifactIdentityDigest",
                "componentArtifactDigest",
                "controlArtifactDigest",
                "installedRootHash",
                "requestDigest",
            )
        )
        or (status_value == "ready" and not all(ID_PATTERN.fullmatch(value) for value in ready_ids))
        or (status_value == "provisioning" and any(ready_ids))
    ):
        raise ParentControlError("operation_failed")
    _parse_time(state.get("createdAt"))
    _parse_time(state.get("expiresAt"))
    return state


def _match_state(
    state: Mapping[str, object],
    session: Mapping[str, object],
    *,
    installed_root: Path,
) -> None:
    if (
        state.get("caseId") != session.get("caseId")
        or state.get("sessionRef") != session.get("sessionRef")
        or state.get("expiresAt") != session.get("expiresAt")
        or state.get("installedRootHash") != session.get("installedRootHash")
        or state.get("artifactIdentityDigest") != session.get("artifactIdentityDigest")
        or state.get("componentArtifactDigest") != session.get("componentArtifactDigest")
        or state.get("controlArtifactDigest") != _control_artifact_digest(installed_root)
    ):
        raise ParentControlError("operation_failed")


def _fixture_document(state: Mapping[str, object], *, include_ids: bool) -> dict[str, object]:
    document = {
        "artifactId": state["artifactId"],
        "caseId": state["caseId"],
        "contractVersion": CONTRACT_VERSION,
        "expiresAt": state["expiresAt"],
        "idempotencyKey": state["idempotencyKey"],
        "namespace": state["namespace"],
        "originRef": state["originRef"],
        "ownerId": state["ownerId"],
        "requestDigest": state["requestDigest"],
        "scopeKind": (
            "synthetic_local_qa"
            if str(state["ownerId"]).startswith("qa_owner_")
            else "selected_synthetic_account_qa"
        ),
    }
    if include_ids:
        document.update(
            {
                "projectId": state["projectId"],
                "runId": state["runId"],
                "workId": state["workId"],
                "workerId": state["workerId"],
            }
        )
    return document


def _fixture_document_with_attestation(
    state: Mapping[str, object],
    session: Mapping[str, object],
    *,
    include_ids: bool,
) -> dict[str, object]:
    document = _fixture_document(state, include_ids=include_ids)
    if document["scopeKind"] == "selected_synthetic_account_qa":
        canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
        document["ownerAttestation"] = "sha256:" + hmac.new(
            str(session["caseToken"]).encode("utf-8"),
            ("glasshive-fixture-owner-v1\0" + canonical).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    return document


def _private_values(
    state: Mapping[str, object], session: Mapping[str, object], db_path: Path
) -> tuple[str, ...]:
    return tuple(
        str(value)
        for value in (
            session.get("caseToken"),
            session.get("sessionRef"),
            session.get("artifactIdentityDigest"),
            session.get("componentArtifactDigest"),
            state.get("namespace"),
            state.get("ownerId"),
            state.get("projectId"),
            state.get("workerId"),
            state.get("workId"),
            state.get("runId"),
            state.get("artifactId"),
            db_path,
        )
        if str(value or "")
    )


def _invoke_fixture(
    *,
    operation: str,
    state: Mapping[str, object],
    session: Mapping[str, object],
    installed_root: Path,
    db_path: Path,
    database_identity: tuple[
        tuple[int, ...], tuple[tuple[int, ...], ...]
    ] | None = None,
) -> tuple[dict[str, object], dict[str, object] | None]:
    expected_identity = database_identity
    if expected_identity is None:
        _path, expected_identity = _database_path_identity(str(db_path))
    _assert_database_path_identity(db_path, expected_identity)
    runtime = _runtime_root(installed_root)
    repository = Path(__file__).resolve().parents[2]
    environment = _clean_child_environment(
        runtime_root=runtime, repository_root=repository, db_path=db_path
    )
    environment["VIVENTIUM_GLASSHIVE_QA_FIXTURE_SECRET"] = str(
        session["caseToken"]
    )
    result = _run_private_json(
        argv=[_python_binary(), "-m", "scripts.viventium.glasshive_qa_fixture", operation],
        cwd=repository,
        env=environment,
        document=_fixture_document_with_attestation(
            state, session, include_ids=operation == "destroy"
        ),
        private_values=_private_values(state, session, db_path),
        receipt=operation == "provision",
    )
    _assert_database_path_identity(db_path, expected_identity)
    return result


def _control_document(
    *,
    operation: str,
    state: Mapping[str, object],
    session: Mapping[str, object],
    boundary: str | None = None,
    ttl_seconds: int | None = None,
    control_ref: str | None = None,
) -> dict[str, object]:
    base: dict[str, object] = {
        "candidateDigest": session["artifactIdentityDigest"],
        "contractVersion": CONTRACT_VERSION,
        "caseId": state["caseId"],
        "caseToken": session["caseToken"],
        "componentArtifactDigest": session["componentArtifactDigest"],
        "sessionRef": session["sessionRef"],
    }
    if operation == "arm":
        assert boundary is not None and ttl_seconds is not None
        selected_owner = not str(state["ownerId"]).startswith("qa_owner_")
        base.update(
            {
                "artifactId": (
                    state["artifactId"] if boundary in ARTIFACT_SCOPED_BOUNDARIES else ""
                ),
                "boundary": boundary,
                "ownerId": state["ownerId"],
                "parameters": {},
                "runId": state["runId"] if boundary in RUN_SCOPED_BOUNDARIES else "",
                "scopeKind": (
                    "selected_synthetic_account_qa"
                    if selected_owner
                    else "synthetic_local_qa"
                ),
                "ttlSeconds": ttl_seconds,
                "workId": state["workId"],
            }
        )
        if selected_owner:
            attested_scope = {
                "artifactId": state["artifactId"],
                "candidateDigest": session["artifactIdentityDigest"],
                "caseId": state["caseId"],
                "componentArtifactDigest": session["componentArtifactDigest"],
                "ownerId": state["ownerId"],
                "runId": state["runId"],
                "sessionRef": session["sessionRef"],
                "workId": state["workId"],
            }
            canonical = json.dumps(
                attested_scope, sort_keys=True, separators=(",", ":")
            )
            base["fixtureAttestation"] = "sha256:" + hmac.new(
                str(session["caseToken"]).encode("utf-8"),
                ("glasshive-fixture-control-v1\0" + canonical).encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
    elif operation == "clear":
        assert control_ref is not None
        base["controlRef"] = control_ref
    return base


def _invoke_control(
    *,
    operation: str,
    document: Mapping[str, object],
    state: Mapping[str, object],
    session: Mapping[str, object],
    installed_root: Path,
    db_path: Path,
    authority: Mapping[str, str],
    database_identity: tuple[
        tuple[int, ...], tuple[tuple[int, ...], ...]
    ] | None = None,
) -> dict[str, object]:
    expected_identity = database_identity
    if expected_identity is None:
        _path, expected_identity = _database_path_identity(str(db_path))
    _assert_database_path_identity(db_path, expected_identity)
    runtime = _runtime_root(installed_root)
    repository = Path(__file__).resolve().parents[2]
    environment = _clean_child_environment(
        runtime_root=runtime, repository_root=repository, db_path=db_path
    )
    environment.update(authority)
    public, private = _run_private_json(
        argv=[_python_binary(), "-m", "workers_projects_runtime.local_qa_control", operation],
        cwd=runtime,
        env=environment,
        document=document,
        private_values=_private_values(state, session, db_path),
    )
    _assert_database_path_identity(db_path, expected_identity)
    if private is not None:
        raise ParentControlError("operation_failed")
    return public


def _scope_hashes(
    state: Mapping[str, object], boundary: str
) -> dict[str, str]:
    return {
        "owner": _nested_scope_hash("owner", str(state["ownerId"])),
        "work": _nested_scope_hash("work", str(state["workId"])),
        "run": (
            _nested_scope_hash("run", str(state["runId"]))
            if boundary in RUN_SCOPED_BOUNDARIES
            else ""
        ),
        "artifact": (
            _nested_scope_hash("artifact", str(state["artifactId"]))
            if boundary in ARTIFACT_SCOPED_BOUNDARIES
            else ""
        ),
    }


def _validate_control(
    row: object,
    state: Mapping[str, object],
    *,
    boundary: str | None = None,
) -> dict[str, object]:
    required = {
        "boundary",
        "caseId",
        "contractVersion",
        "controlRef",
        "expiresAt",
        "operation",
        "scopeHashes",
        "status",
    }
    if not isinstance(row, dict) or not required.issubset(row):
        raise ParentControlError("operation_failed")
    allowed = required | {"clearedAt", "consumedAt"}
    selected = str(row.get("boundary") or "")
    if (
        set(row) - allowed
        or row.get("contractVersion") != 1
        or row.get("caseId") != state.get("caseId")
        or selected not in CASE_BOUNDARIES[str(state["caseId"])]
        or (boundary is not None and selected != boundary)
        or not CONTROL_REF_PATTERN.fullmatch(str(row.get("controlRef") or ""))
        or row.get("scopeHashes") != _scope_hashes(state, selected)
        or row.get("status") not in {
            "armed",
            "already_armed",
            "consumed",
            "cleared",
            "expired",
        }
    ):
        raise ParentControlError("operation_failed")
    _parse_time(row.get("expiresAt"))
    for key in ("clearedAt", "consumedAt"):
        if row.get(key) is not None:
            _parse_time(row.get(key))
    return dict(row)


def _validate_query(
    payload: object, state: Mapping[str, object]
) -> list[dict[str, object]]:
    fields = {
        "caseId",
        "contractVersion",
        "controls",
        "count",
        "operation",
        "status",
        "truncated",
    }
    if (
        not isinstance(payload, dict)
        or set(payload) != fields
        or payload.get("contractVersion") != 1
        or payload.get("operation") != "query"
        or payload.get("status") != "ok"
        or payload.get("caseId") != state.get("caseId")
        or payload.get("truncated") is not False
        or not isinstance(payload.get("controls"), list)
        or isinstance(payload.get("count"), bool)
        or payload.get("count") != len(payload["controls"])
    ):
        raise ParentControlError("operation_failed")
    rows = [_validate_control(row, state) for row in payload["controls"]]
    refs = [str(row["controlRef"]) for row in rows]
    if len(refs) != len(set(refs)):
        raise ParentControlError("operation_failed")
    return rows


def _redacted_state(state: Mapping[str, object]) -> dict[str, object]:
    return {
        "caseId": state["caseId"],
        "contractVersion": CONTRACT_VERSION,
        "expiresAt": state["expiresAt"],
        "fixtureRef": state["fixtureRef"],
        "operation": "prepare",
        "scopeHashes": {
            "artifact": _nested_scope_hash("artifact", str(state["artifactId"])),
            "owner": _nested_scope_hash("owner", str(state["ownerId"])),
            "run": _nested_scope_hash("run", str(state["runId"])),
            "work": _nested_scope_hash("work", str(state["workId"])),
        },
        "status": "ready",
    }


def _common_active(
    *,
    parent_state_path: Path,
    session_state_path: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    local_qa_request_path: Path,
    runtime_env_path: Path,
    now: datetime | None = None,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, str],
    Path,
    tuple[tuple[int, ...], tuple[tuple[int, ...], ...]],
]:
    session = _active_session(
        session_state_path=session_state_path,
        installed_root=installed_root,
        artifact_identity_path=artifact_identity_path,
        local_qa_request_path=local_qa_request_path,
        now=now,
    )
    if session.get("caseId") not in CASE_BOUNDARIES:
        raise ParentControlError("operation_failed")
    state = _state(parent_state_path)
    _match_state(state, session, installed_root=installed_root)
    if state.get("status") != "ready":
        raise ParentControlError("operation_failed")
    authority, db_path, database_identity = _runtime_authority_bound(
        runtime_env_path, session
    )
    return state, session, authority, db_path, database_identity


def _common_cleanup(
    *,
    parent_state_path: Path,
    session_state_path: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    local_qa_request_path: Path,
    runtime_env_path: Path,
    now: datetime | None = None,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, str],
    Path,
    tuple[tuple[int, ...], tuple[tuple[int, ...], ...]],
]:
    del now
    session = _raw_session(session_state_path)
    if (
        session.get("caseId") not in CASE_BOUNDARIES
        or session.get("installedRootHash") != _root_hash(installed_root)
    ):
        raise ParentControlError("operation_failed")
    try:
        session_module = _session_module()
        session_module._require_local_qa_request(local_qa_request_path)
        candidate_digest, component_digest = session_module._artifact_digests(
            artifact_identity_path, installed_root
        )
    except (OSError, RuntimeError, ValueError) as exc:
        raise ParentControlError("operation_failed") from exc
    if (
        not HASH_PATTERN.fullmatch(str(candidate_digest or ""))
        or not HASH_PATTERN.fullmatch(str(component_digest or ""))
    ):
        raise ParentControlError("operation_failed")
    state = _state(parent_state_path)
    if (
        state.get("status") != "ready"
        or state.get("caseId") != session.get("caseId")
        or state.get("sessionRef") != session.get("sessionRef")
        or state.get("expiresAt") != session.get("expiresAt")
        or state.get("installedRootHash") != session.get("installedRootHash")
        or state.get("artifactIdentityDigest")
        != session.get("artifactIdentityDigest")
        or state.get("componentArtifactDigest")
        != session.get("componentArtifactDigest")
    ):
        raise ParentControlError("operation_failed")
    runtime_values = _parse_runtime_env(runtime_env_path)
    db_path, database_identity = _database_path_identity(
        str(runtime_values.get("WPR_DB_PATH") or "")
    )
    authority = {
        "VIVENTIUM_GLASSHIVE_LOCAL_QA_MODE": str(session["mode"]),
        "VIVENTIUM_LOCAL_QA_CANDIDATE_DIGEST": str(candidate_digest),
        "VIVENTIUM_LOCAL_QA_CASE_ID": str(session["caseId"]),
        "VIVENTIUM_LOCAL_QA_CASE_TOKEN": str(session["caseToken"]),
        "VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST": str(component_digest),
        "VIVENTIUM_LOCAL_QA_SESSION_REF": str(session["sessionRef"]),
    }
    return state, session, authority, db_path, database_identity


def prepare_fixture(
    *,
    case_id: str,
    owner_id: str,
    parent_state_path: Path,
    session_state_path: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    local_qa_request_path: Path,
    runtime_env_path: Path,
    now: datetime | None = None,
    token_hex: Callable[[int], str] = secrets.token_hex,
) -> dict[str, object]:
    checked_at = (now or _utc_now()).astimezone(timezone.utc)
    session = _active_session(
        session_state_path=session_state_path,
        installed_root=installed_root,
        artifact_identity_path=artifact_identity_path,
        local_qa_request_path=local_qa_request_path,
        now=checked_at,
    )
    if case_id not in CASE_BOUNDARIES or session.get("caseId") != case_id:
        raise ParentControlError("operation_failed")
    if not ID_PATTERN.fullmatch(str(owner_id or "")):
        raise ParentControlError("operation_failed")
    authority, db_path, database_identity = _runtime_authority_bound(
        runtime_env_path, session
    )
    del authority
    if parent_state_path.exists() or parent_state_path.is_symlink():
        state = _state(parent_state_path)
        _match_state(state, session, installed_root=installed_root)
        if state.get("ownerId") != owner_id:
            raise ParentControlError("operation_failed")
    else:
        namespace = token_hex(16)
        if not NAMESPACE_PATTERN.fullmatch(namespace):
            raise ParentControlError("operation_failed")
        artifact_id = "artifact_sha256:" + hashlib.sha256(
            f"glasshive-local-qa-artifact\0{namespace}".encode()
        ).hexdigest()
        state = {
            "artifactId": artifact_id,
            "artifactIdentityDigest": session["artifactIdentityDigest"],
            "caseId": case_id,
            "componentArtifactDigest": session["componentArtifactDigest"],
            "contractVersion": CONTRACT_VERSION,
            "controlArtifactDigest": _control_artifact_digest(installed_root),
            "createdAt": _iso(checked_at),
            "expiresAt": session["expiresAt"],
            "fixtureRef": "pwk_fixture_sha256:" + hashlib.sha256(namespace.encode()).hexdigest(),
            "idempotencyKey": "qa_idem_" + hashlib.sha256(
                f"{session['sessionRef']}\0{namespace}".encode()
            ).hexdigest(),
            "installedRootHash": session["installedRootHash"],
            "namespace": namespace,
            "originRef": "qa_origin_" + namespace,
            "ownerId": owner_id,
            "projectId": "",
            "requestDigest": _sha256("fixture-request", f"{case_id}\0{namespace}"),
            "runId": "",
            "sessionRef": session["sessionRef"],
            "status": "provisioning",
            "workId": "",
            "workerId": "",
        }
        _write_private_json(parent_state_path, state)
    public, private = _invoke_fixture(
        operation="provision",
        state=state,
        session=session,
        installed_root=installed_root,
        db_path=db_path,
        database_identity=database_identity,
    )
    expected_public = {
        "contractVersion": CONTRACT_VERSION,
        "fixtureRef": state["fixtureRef"],
        "operation": "provision",
        "status": "ready",
    }
    private_fields = {
        "artifactId",
        "caseId",
        "namespace",
        "ownerId",
        "projectId",
        "runId",
        "workId",
        "workerId",
    }
    if public != expected_public or not isinstance(private, dict) or set(private) != private_fields:
        raise ParentControlError("operation_failed")
    for key in ("artifactId", "caseId", "namespace", "ownerId"):
        if private.get(key) != state.get(key):
            raise ParentControlError("operation_failed")
    for key in ("projectId", "workerId", "workId", "runId"):
        value = str(private.get(key) or "")
        if not ID_PATTERN.fullmatch(value):
            raise ParentControlError("operation_failed")
        existing = str(state.get(key) or "")
        if existing and existing != value:
            raise ParentControlError("operation_failed")
        state[key] = value
    state["status"] = "ready"
    _write_private_json(parent_state_path, state)
    return _redacted_state(state)


def arm_fault(
    *,
    boundary: str,
    ttl_seconds: int,
    **common: object,
) -> dict[str, object]:
    now = common.get("now")
    state, session, authority, db_path, database_identity = _common_active(**common)
    if boundary not in CASE_BOUNDARIES[str(state["caseId"])]:
        raise ParentControlError("operation_failed")
    if (
        isinstance(ttl_seconds, bool)
        or not isinstance(ttl_seconds, int)
        or not 1 <= ttl_seconds <= 3600
    ):
        raise ParentControlError("operation_failed")
    checked_at = (now or _utc_now()).astimezone(timezone.utc)
    if checked_at + timedelta(seconds=ttl_seconds) > _parse_time(session["expiresAt"]):
        raise ParentControlError("operation_failed")
    document = _control_document(
        operation="arm",
        state=state,
        session=session,
        boundary=boundary,
        ttl_seconds=ttl_seconds,
    )
    receipt = _invoke_control(
        operation="arm",
        document=document,
        state=state,
        session=session,
        installed_root=common["installed_root"],
        db_path=db_path,
        authority=authority,
        database_identity=database_identity,
    )
    return _validate_control(receipt, state, boundary=boundary)


def query_faults(
    *, boundary: str | None = None, **common: object
) -> dict[str, object]:
    state, session, authority, db_path, database_identity = _common_active(**common)
    if boundary is not None and boundary not in CASE_BOUNDARIES[str(state["caseId"])]:
        raise ParentControlError("operation_failed")
    result = _invoke_control(
        operation="query",
        document=_control_document(operation="query", state=state, session=session),
        state=state,
        session=session,
        installed_root=common["installed_root"],
        db_path=db_path,
        authority=authority,
        database_identity=database_identity,
    )
    rows = _validate_query(result, state)
    if boundary is not None:
        rows = [row for row in rows if row["boundary"] == boundary]
    return {
        "caseId": state["caseId"],
        "contractVersion": CONTRACT_VERSION,
        "controls": rows,
        "count": len(rows),
        "operation": "query",
        "status": "ok",
    }


def clear_faults(
    *, boundary: str | None = None, **common: object
) -> dict[str, object]:
    state, session, authority, db_path, database_identity = _common_active(**common)
    if boundary is not None and boundary not in CASE_BOUNDARIES[str(state["caseId"])]:
        raise ParentControlError("operation_failed")
    query = _invoke_control(
        operation="query",
        document=_control_document(operation="query", state=state, session=session),
        state=state,
        session=session,
        installed_root=common["installed_root"],
        db_path=db_path,
        authority=authority,
        database_identity=database_identity,
    )
    rows = _validate_query(query, state)
    targets = [
        row
        for row in rows
        if row["status"] in {"armed", "already_armed"}
        and (boundary is None or row["boundary"] == boundary)
    ]
    cleared = 0
    for row in targets:
        receipt = _invoke_control(
            operation="clear",
            document=_control_document(
                operation="clear",
                state=state,
                session=session,
                control_ref=str(row["controlRef"]),
            ),
            state=state,
            session=session,
            installed_root=common["installed_root"],
            db_path=db_path,
            authority=authority,
            database_identity=database_identity,
        )
        validated = _validate_control(receipt, state, boundary=str(row["boundary"]))
        if validated["status"] != "cleared":
            raise ParentControlError("operation_failed")
        cleared += 1
    return {
        "caseId": state["caseId"],
        "cleared": cleared,
        "contractVersion": CONTRACT_VERSION,
        "operation": "clear",
        "status": "ok",
    }


def cleanup_fixture(**common: object) -> dict[str, object]:
    session_module, source_snapshots = _cleanup_source_snapshots(
        parent_state_path=common["parent_state_path"],
        session_state_path=common["session_state_path"],
        artifact_identity_path=common["artifact_identity_path"],
        local_qa_request_path=common["local_qa_request_path"],
        runtime_env_path=common["runtime_env_path"],
    )
    state, session, authority, db_path, database_identity = _common_cleanup(**common)
    _assert_cleanup_sources(session_module, source_snapshots)
    cleaned = _invoke_control(
        operation="cleanup",
        document=_control_document(operation="cleanup", state=state, session=session),
        state=state,
        session=session,
        installed_root=common["installed_root"],
        db_path=db_path,
        authority=authority,
        database_identity=database_identity,
    )
    _assert_cleanup_sources(session_module, source_snapshots)
    _assert_database_path_identity(db_path, database_identity)
    cleanup_fields = {
        "artifactReplacementCleared",
        "caseId",
        "contractVersion",
        "expiredControls",
        "operation",
        "removedAuditEvents",
        "removedControls",
        "status",
    }
    if (
        set(cleaned) != cleanup_fields
        or cleaned.get("contractVersion") != 1
        or cleaned.get("operation") != "cleanup"
        or cleaned.get("status") != "clean"
        or cleaned.get("caseId") != state.get("caseId")
        or any(
            isinstance(cleaned.get(key), bool) or not isinstance(cleaned.get(key), int)
            for key in (
                "artifactReplacementCleared",
                "expiredControls",
                "removedAuditEvents",
                "removedControls",
            )
        )
    ):
        raise ParentControlError("operation_failed")
    public, private = _invoke_fixture(
        operation="destroy",
        state=state,
        session=session,
        installed_root=common["installed_root"],
        db_path=db_path,
        database_identity=database_identity,
    )
    _assert_cleanup_sources(session_module, source_snapshots)
    _assert_database_path_identity(db_path, database_identity)
    if private is not None or set(public) != {
        "contractVersion",
        "fixtureRef",
        "operation",
        "removed",
        "status",
    }:
        raise ParentControlError("operation_failed")
    if (
        public.get("contractVersion") != 1
        or public.get("fixtureRef") != state.get("fixtureRef")
        or public.get("operation") != "destroy"
        or public.get("status") != "clean"
        or not isinstance(public.get("removed"), dict)
    ):
        raise ParentControlError("operation_failed")
    parent_path, parent_label, parent_max, parent_snapshot = source_snapshots["parent"]
    try:
        session_module._unlink_private_file_snapshot(
            parent_path,
            parent_snapshot,
            label=parent_label,
            max_bytes=parent_max,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        raise ParentControlError("operation_failed") from exc
    return {
        "caseId": state["caseId"],
        "contractVersion": CONTRACT_VERSION,
        "fixtureRef": state["fixtureRef"],
        "operation": "cleanup",
        "removed": public["removed"],
        "status": "clean",
    }


def session_clearable(*, parent_state_path: Path) -> bool:
    if parent_state_path.is_symlink() or parent_state_path.exists():
        return False
    return True


def _paths_from_environment() -> dict[str, Path]:
    result: dict[str, Path] = {}
    for name, variable in PATH_ENV.items():
        raw = str(os.environ.get(variable, "") or "").strip()
        if not raw or not Path(raw).is_absolute():
            raise ParentControlError("operation_failed")
        result[name] = Path(raw)
    return result


def main(argv: Iterable[str] | None = None) -> int:
    parser = PrivateArgumentParser(allow_abbrev=False)
    subcommands = parser.add_subparsers(dest="command", required=True)
    prepare = subcommands.add_parser("prepare", allow_abbrev=False)
    prepare.add_argument("--case-id", choices=sorted(CASE_BOUNDARIES), required=True)
    prepare.add_argument("--owner-scope-stdin", action="store_true")
    arm = subcommands.add_parser("arm", allow_abbrev=False)
    arm.add_argument("--boundary", required=True)
    arm.add_argument("--ttl-seconds", type=int, default=60)
    for name in ("query", "clear"):
        command = subcommands.add_parser(name, allow_abbrev=False)
        command.add_argument("--boundary")
    subcommands.add_parser("cleanup", allow_abbrev=False)
    subcommands.add_parser("clear-gate", allow_abbrev=False)
    values = list(argv) if argv is not None else sys.argv[1:]
    try:
        _reject_duplicate_options(values)
        args = parser.parse_args(values)
        paths = _paths_from_environment()
        if args.command in {"prepare", "arm"}:
            _session_module().require_restart_ready(
                state_path=paths["session_state_path"],
                installed_root=paths["installed_root"],
                artifact_identity_path=paths["artifact_identity_path"],
                local_qa_request_path=paths["local_qa_request_path"],
            )
        if args.command == "prepare":
            if args.owner_scope_stdin is not True:
                raise ParentControlError("operation_failed")
            librechat_env_raw = str(
                os.environ.get(LIBRECHAT_ENV_PATH_ENV, "") or ""
            ).strip()
            if not librechat_env_raw or not Path(librechat_env_raw).is_absolute():
                raise ParentControlError("operation_failed")
            session = _active_session(
                session_state_path=paths["session_state_path"],
                installed_root=paths["installed_root"],
                artifact_identity_path=paths["artifact_identity_path"],
                local_qa_request_path=paths["local_qa_request_path"],
            )
            signing_secret = str(
                _parse_runtime_env(Path(librechat_env_raw)).get("JWT_SECRET") or ""
            )
            owner_scope = _verify_selected_owner_scope(
                _read_selected_owner_scope_stdin(),
                session=session,
                signing_secret=signing_secret,
            )
            result = prepare_fixture(
                case_id=args.case_id,
                owner_id=owner_scope["ownerId"],
                **paths,
            )
        elif args.command == "arm":
            result = arm_fault(
                boundary=args.boundary, ttl_seconds=args.ttl_seconds, **paths
            )
        elif args.command == "query":
            result = query_faults(boundary=args.boundary, **paths)
        elif args.command == "clear":
            result = clear_faults(boundary=args.boundary, **paths)
        elif args.command == "cleanup":
            result = cleanup_fixture(**paths)
        else:
            result = {"clearable": session_clearable(parent_state_path=paths["parent_state_path"])}
            if not result["clearable"]:
                raise ParentControlError("operation_failed")
    except Exception:
        sys.stderr.write('{"error":"operation_failed"}\n')
        return 2
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
