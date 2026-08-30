#!/usr/bin/env python3
"""Own the installed EMO-UC-048 synthetic fixture and fault-control lifecycle."""

from __future__ import annotations

import argparse
import hashlib
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
import time
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from urllib.parse import urlsplit

CASE_ID = "EMO-UC-048"
CASE_MODE = "emo_uc_048"
CONTRACT_VERSION = 1
BOUNDARIES = (
    "cortex_ledger_first_write",
    "web_replay_persistence",
    "web_redis_publish_ack",
    "telegram_promoted_parent_presentation",
)
HASH_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")
ISO_MILLIS_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}\+00:00$"
)
OBJECT_ID_PATTERN = re.compile(r"^[a-f0-9]{24}$")
NAMESPACE_PATTERN = re.compile(r"^[a-f0-9]{32}$")
FIXTURE_REF_PATTERN = re.compile(r"^emo048_fixture_[a-f0-9]{24}$")
CONTROL_ID_PATTERN = re.compile(r"^emo048_[A-Za-z0-9-]{16,80}$")
CONTROL_STATES = {"armed", "consumed", "cleared", "expired"}
PRIVATE_INPUT_MAX_BYTES = 8 * 1024
CHILD_OUTPUT_MAX_BYTES = 64 * 1024
CHILD_ERROR_MAX_BYTES = 16 * 1024
RUNTIME_ENV_MAX_BYTES = 64 * 1024
PARENT_STATE_MAX_BYTES = 16 * 1024
TRUSTED_NODE_CANDIDATES = (
    Path("/opt/homebrew/opt/node@24/bin/node"),
    Path("/usr/local/opt/node@24/bin/node"),
)
PARENT_STATE_FIELDS = {
    "artifactIdentityDigest",
    "caseId",
    "caseTokenHash",
    "componentArtifactDigest",
    "contractVersion",
    "conversationId",
    "conversationScopeHash",
    "email",
    "expiresAt",
    "fixtureRef",
    "installedRootHash",
    "ownerId",
    "ownerScopeHash",
    "parentMessageId",
    "parentScopeHash",
    "phase",
    "preparedAt",
    "sessionRef",
}
CONTROL_ROW_FIELDS = {
    "armedAt",
    "audit",
    "boundary",
    "clearedAt",
    "consumedAt",
    "controlId",
    "conversationScopeHash",
    "expiresAt",
    "ownerScopeHash",
    "parentScopeHash",
    "purgeAt",
    "state",
    "syntheticScope",
}
RunPrivateJson = Callable[..., object]


class PrivateArgumentParser(argparse.ArgumentParser):
    """Reject invalid arguments without echoing their values."""

    def error(self, message: str) -> None:
        del message
        raise ValueError("operation_failed")


class DuplicateJsonKeyError(ValueError):
    """Reject ambiguous JSON instead of accepting the last duplicate key."""


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError("duplicate JSON key")
        result[key] = value
    return result


def _loads_strict_json(raw: str) -> object:
    return json.loads(raw, object_pairs_hook=_unique_json_object)


def _reject_duplicate_options(argv: Iterable[str]) -> None:
    seen: set[str] = set()
    for argument in argv:
        if not argument.startswith("--"):
            continue
        option = argument.split("=", 1)[0]
        if option in seen:
            raise ValueError("operation_failed")
        seen.add(option)


def _load_path(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("operation_failed")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _session_module() -> ModuleType:
    return _load_path(
        Path(__file__).with_name("local_qa_runtime_control.py"),
        "viventium_local_qa_runtime_control_for_emo048",
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: object) -> datetime:
    rendered = str(value or "")
    if not ISO_MILLIS_PATTERN.fullmatch(rendered):
        raise ValueError("operation_failed")
    try:
        parsed = datetime.fromisoformat(rendered)
    except ValueError as exc:
        raise ValueError("operation_failed") from exc
    if parsed.tzinfo is None:
        raise ValueError("operation_failed")
    return parsed.astimezone(timezone.utc)


def _sha256(label: str, value: str) -> str:
    return "sha256:" + hashlib.sha256(f"{label}\0{value}".encode()).hexdigest()


def _librechat_root(installed_root: Path) -> Path:
    root = installed_root.expanduser().resolve(strict=True)
    candidate = root / "viventium_v0_4" / "LibreChat"
    if not candidate.is_dir() or not (candidate / "package.json").is_file():
        raise ValueError("installed LibreChat is unavailable")
    return candidate


def _control_script(installed_root: Path) -> Path:
    script = _librechat_root(installed_root) / "scripts" / "viventium-cortex-fault-control.js"
    if not script.is_file():
        raise ValueError("installed LibreChat fault control is unavailable")
    return script


def _node_binary() -> str:
    for candidate in TRUSTED_NODE_CANDIDATES:
        try:
            if not candidate.is_absolute():
                continue
            exact = candidate.resolve(strict=True)
            details = exact.stat()
            if (
                exact.is_file()
                and stat.S_ISREG(details.st_mode)
                and details.st_uid in {0, os.getuid()}
                and stat.S_IMODE(details.st_mode) & 0o022 == 0
                and os.access(exact, os.X_OK)
            ):
                return str(exact)
        except (OSError, RuntimeError):
            continue
    raise ValueError("installed Node runtime is unavailable")


def _parse_env_file(path: Path) -> dict[str, str]:
    try:
        raw = _session_module()._read_private_file(
            path,
            label="configured LibreChat environment",
            max_bytes=RUNTIME_ENV_MAX_BYTES,
        )
        lines = raw.decode("utf-8", errors="strict").splitlines()
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError("configured LibreChat environment is unavailable") from exc
    values: dict[str, str] = {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.removeprefix("export ")
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        normalized_key = key.strip()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", normalized_key):
            continue
        if normalized_key in values:
            raise ValueError("configured LibreChat environment is invalid")
        try:
            parts = shlex.split(raw_value, comments=False, posix=True)
        except ValueError as exc:
            raise ValueError("configured LibreChat environment is invalid") from exc
        values[normalized_key] = parts[0] if len(parts) == 1 else raw_value.strip("'\"")
    return values


def _local_mongo_uri(runtime_env_path: Path) -> str:
    values = _parse_env_file(runtime_env_path)
    uri = values.get("MONGO_URI", "").strip()
    if not uri:
        port = values.get("VIVENTIUM_LOCAL_MONGO_PORT", "").strip()
        database = values.get("VIVENTIUM_LOCAL_MONGO_DB", "").strip()
        if re.fullmatch(r"[0-9]{2,5}", port) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", database):
            uri = f"mongodb://127.0.0.1:{port}/{database}"
    try:
        parsed = urlsplit(uri)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("configured Mongo must be local") from exc
    host = parsed.hostname
    database = parsed.path.removeprefix("/")
    if host == "::1" and port is not None:
        authority = f"[::1]:{port}"
    elif host in {"127.0.0.1", "localhost"} and port is not None:
        authority = f"{host}:{port}"
    else:
        authority = ""
    canonical = f"mongodb://{authority}/{database}"
    if (
        parsed.scheme != "mongodb"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not authority
        or port is None
        or not 1 <= port <= 65535
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", database)
        or uri != canonical
    ):
        raise ValueError("configured Mongo must be local")
    return uri


def _sanitize_child_environment(values: dict[str, str]) -> dict[str, str]:
    allowed = {
        "MONGO_URI",
        "VIVENTIUM_LIBRECHAT_ROOT",
        "VIVENTIUM_LOCAL_QA_CASE_ID",
        "VIVENTIUM_LOCAL_QA_CASE_TOKEN",
        "VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST",
        "VIVENTIUM_LOCAL_QA_MODE",
        "VIVENTIUM_LOCAL_QA_SESSION_REF",
    }
    result = {
        name: str(value)
        for name, value in values.items()
        if name in allowed and isinstance(value, str)
    }
    result["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    result["TZ"] = "UTC"
    return result


def _base_environment(mongo_uri: str, librechat_root: Path) -> dict[str, str]:
    return _sanitize_child_environment(
        {
            "MONGO_URI": mongo_uri,
            "VIVENTIUM_LIBRECHAT_ROOT": str(librechat_root),
        }
    )


def _run_private_json(
    *,
    argv: list[str],
    cwd: Path,
    env: dict[str, str],
    document: dict[str, object],
    private_values: Iterable[str],
    fixture: dict[str, object] | None = None,
    private_fd: bool = False,
) -> object:
    del fixture
    raw = json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(raw) > PRIVATE_INPUT_MAX_BYTES:
        raise ValueError("operation_failed")
    sensitive = tuple(value.encode("utf-8") for value in private_values if value)
    child_env = _sanitize_child_environment(env)

    def execute(
        effective_argv: list[str], *, descriptor: int | None = None
    ) -> tuple[int, bytes, bytes]:
        rendered_argv = [str(argument) for argument in effective_argv]
        encoded_argv = [argument.encode("utf-8") for argument in rendered_argv]
        if any(value in argument for value in sensitive for argument in encoded_argv):
            raise ValueError("operation_failed")
        process: subprocess.Popen[bytes] | None = None
        selector: selectors.BaseSelector | None = None

        def terminate() -> None:
            if process is None or process.poll() is not None:
                return
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                try:
                    process.kill()
                except OSError:
                    pass
            try:
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                pass

        try:
            process = subprocess.Popen(
                rendered_argv,
                cwd=str(cwd),
                env=child_env,
                stdin=subprocess.DEVNULL if descriptor is not None else subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                pass_fds=(descriptor,) if descriptor is not None else (),
                start_new_session=True,
            )
            if process.stdin is not None:
                try:
                    process.stdin.write(raw)
                    process.stdin.close()
                except (BrokenPipeError, OSError):
                    terminate()
                    raise ValueError("operation_failed")
            if process.stdout is None or process.stderr is None:
                terminate()
                raise ValueError("operation_failed")
            stdout = bytearray()
            stderr = bytearray()
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ, (stdout, CHILD_OUTPUT_MAX_BYTES))
            selector.register(process.stderr, selectors.EVENT_READ, (stderr, CHILD_ERROR_MAX_BYTES))
            deadline = time.monotonic() + 60
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    terminate()
                    raise ValueError("operation_failed")
                events = selector.select(min(remaining, 0.25))
                if not events and process.poll() is not None:
                    events = [(key, selectors.EVENT_READ) for key in selector.get_map().values()]
                for key, _mask in events:
                    target, limit = key.data
                    chunk = os.read(key.fileobj.fileno(), min(16 * 1024, limit + 1 - len(target)))
                    if chunk:
                        target.extend(chunk)
                        if len(target) > limit:
                            terminate()
                            raise ValueError("operation_failed")
                    else:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
            returncode = process.wait(timeout=max(0.01, deadline - time.monotonic()))
            return returncode, bytes(stdout), bytes(stderr)
        except (OSError, subprocess.SubprocessError, UnicodeError, ValueError) as exc:
            terminate()
            raise ValueError("operation_failed") from exc
        finally:
            if selector is not None:
                selector.close()

    if private_fd:
        with tempfile.TemporaryFile(mode="w+b") as channel:
            descriptor = channel.fileno()
            if descriptor < 3 or descriptor > 1024:
                raise ValueError("operation_failed")
            os.fchmod(descriptor, 0o600)
            channel.write(raw)
            channel.flush()
            channel.seek(0)
            returncode, stdout, stderr = execute(
                [*argv, "--scope-fd", str(descriptor)], descriptor=descriptor
            )
    else:
        returncode, stdout, stderr = execute(argv)
    combined = stdout + stderr
    if any(value in combined for value in sensitive):
        raise ValueError("operation_failed")
    if returncode != 0:
        raise ValueError("operation_failed")
    try:
        output = stdout.decode("utf-8", errors="strict")
        stderr.decode("utf-8", errors="strict")
        return _loads_strict_json(output)
    except (UnicodeError, json.JSONDecodeError, DuplicateJsonKeyError) as exc:
        raise ValueError("operation_failed") from exc


def _raw_session(
    *,
    session_state_path: Path,
    installed_root: Path,
) -> dict[str, object]:
    session = _session_module()
    payload = session._read_state(session_state_path)
    if payload.get("caseId") != CASE_ID:
        raise ValueError("an exact EMO-UC-048 session is required")
    if payload.get("installedRootHash") != session._root_hash(installed_root):
        raise ValueError("local-QA session belongs to a different installed candidate")
    return payload


def _active_session(
    *,
    session_state_path: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    local_qa_request_path: Path,
    now: datetime | None,
) -> dict[str, object]:
    session = _session_module()
    payload = session.active_session(
        state_path=session_state_path,
        installed_root=installed_root,
        artifact_identity_path=artifact_identity_path,
        local_qa_request_path=local_qa_request_path,
        now=now,
    )
    if payload.get("caseId") != CASE_ID:
        raise ValueError("an exact active EMO-UC-048 session is required")
    return payload


def _read_parent_state(path: Path) -> dict[str, object]:
    try:
        _raw, payload = _session_module()._read_private_json(
            path,
            label="EMO-UC-048 fixture state",
            max_bytes=PARENT_STATE_MAX_BYTES,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError("EMO-UC-048 fixture state is invalid") from exc
    if not isinstance(payload, dict) or set(payload) != PARENT_STATE_FIELDS:
        raise ValueError("EMO-UC-048 fixture state is invalid")
    if payload.get("contractVersion") != CONTRACT_VERSION or payload.get("caseId") != CASE_ID:
        raise ValueError("EMO-UC-048 fixture state is invalid")
    owner_id = str(payload.get("ownerId") or "")
    conversation_id = str(payload.get("conversationId") or "")
    parent_id = str(payload.get("parentMessageId") or "")
    suffix = conversation_id.removeprefix("emo_uc_048_conversation_")
    if (
        not OBJECT_ID_PATTERN.fullmatch(owner_id)
        or not NAMESPACE_PATTERN.fullmatch(suffix)
        or parent_id != f"emo_uc_048_parent_{suffix}"
        or payload.get("email") != f"emo-uc-048-{suffix}@local-qa.invalid"
        or payload.get("ownerScopeHash") != _sha256("owner", owner_id)
        or payload.get("conversationScopeHash") != _sha256("conversation", conversation_id)
        or payload.get("parentScopeHash") != _sha256("parent", parent_id)
        or not HASH_PATTERN.fullmatch(str(payload.get("artifactIdentityDigest") or ""))
        or not HASH_PATTERN.fullmatch(str(payload.get("componentArtifactDigest") or ""))
        or not HASH_PATTERN.fullmatch(str(payload.get("caseTokenHash") or ""))
        or not FIXTURE_REF_PATTERN.fullmatch(str(payload.get("fixtureRef") or ""))
        or payload.get("phase") not in {"provisioning", "prepared"}
    ):
        raise ValueError("EMO-UC-048 fixture state is invalid")
    expires_at = _parse_time(payload["expiresAt"])
    if payload["expiresAt"] != _session_module()._iso(expires_at):
        raise ValueError("EMO-UC-048 fixture state is invalid")
    return payload


def _match_parent_to_session(
    parent: dict[str, object], session: dict[str, object], *, require_artifact: bool
) -> None:
    expected_token_hash = _sha256("case-token", str(session["caseToken"]))
    if (
        parent.get("sessionRef") != session.get("sessionRef")
        or parent.get("caseTokenHash") != expected_token_hash
        or parent.get("installedRootHash") != session.get("installedRootHash")
        or parent.get("expiresAt") != session.get("expiresAt")
        or parent.get("componentArtifactDigest")
        != session.get("componentArtifactDigest")
        or (
            require_artifact
            and parent.get("artifactIdentityDigest") != session.get("artifactIdentityDigest")
        )
    ):
        raise ValueError("EMO-UC-048 fixture belongs to a different session")


def _fixture_document(state: dict[str, object]) -> dict[str, object]:
    return {
        "fixture": {
            "caseTokenHash": state["caseTokenHash"],
            "componentArtifactDigest": state["componentArtifactDigest"],
            "conversationId": state["conversationId"],
            "conversationScopeHash": state["conversationScopeHash"],
            "email": state["email"],
            "expiresAt": state["expiresAt"],
            "ownerId": state["ownerId"],
            "ownerScopeHash": state["ownerScopeHash"],
            "parentMessageId": state["parentMessageId"],
            "parentScopeHash": state["parentScopeHash"],
        },
        "fixtureRef": state["fixtureRef"],
        "schemaVersion": CONTRACT_VERSION,
    }


def _scope_document(
    state: dict[str, object], *, boundary: str | None = None, ttl_seconds: int | None = None
) -> dict[str, object]:
    document: dict[str, object] = {
        "schemaVersion": CONTRACT_VERSION,
        "scope": {
            "conversationId": state["conversationId"],
            "ownerId": state["ownerId"],
            "parentMessageId": state["parentMessageId"],
        },
    }
    if boundary is not None:
        document["boundary"] = boundary
    if ttl_seconds is not None:
        document["ttlSeconds"] = ttl_seconds
    return document


def _private_values(state: dict[str, object], session: dict[str, object]) -> tuple[str, ...]:
    namespace = str(state["conversationId"]).removeprefix("emo_uc_048_conversation_")
    return (
        str(session["caseToken"]),
        str(state["ownerId"]),
        str(state["conversationId"]),
        str(state["parentMessageId"]),
        str(state["email"]),
        str(state["componentArtifactDigest"]),
        namespace,
    )


def _redacted_fixture(state: dict[str, object]) -> dict[str, object]:
    return {
        "caseId": CASE_ID,
        "expiresAt": state["expiresAt"],
        "fixtureRef": state["fixtureRef"],
        "ownerScopeHash": state["ownerScopeHash"],
        "conversationScopeHash": state["conversationScopeHash"],
        "parentScopeHash": state["parentScopeHash"],
        "sessionRef": state["sessionRef"],
    }


def _runner_environment(
    *,
    runtime_env_path: Path,
    installed_root: Path,
    session: dict[str, object] | None,
    component_artifact_digest: str,
) -> dict[str, str]:
    librechat = _librechat_root(installed_root)
    env = _base_environment(_local_mongo_uri(runtime_env_path), librechat)
    if not HASH_PATTERN.fullmatch(component_artifact_digest):
        raise ValueError("operation_failed")
    env["VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST"] = component_artifact_digest
    if session is not None:
        env.update(
            {
                "VIVENTIUM_LOCAL_QA_CASE_ID": CASE_ID,
                "VIVENTIUM_LOCAL_QA_CASE_TOKEN": str(session["caseToken"]),
                "VIVENTIUM_LOCAL_QA_MODE": CASE_MODE,
                "VIVENTIUM_LOCAL_QA_SESSION_REF": str(session["sessionRef"]),
            }
        )
    return env


def _validate_fixture_receipt(
    result: object, state: dict[str, object], *, action: str
) -> dict[str, object]:
    if not isinstance(result, dict) or set(result) != {
        "action",
        "caseId",
        "fixtureRef",
        "hashes",
        "rows",
        "schemaVersion",
    }:
        raise ValueError("operation_failed")
    expected_hashes = {
        name: state[name]
        for name in (
            "caseTokenHash",
            "ownerScopeHash",
            "conversationScopeHash",
            "parentScopeHash",
        )
    }
    rows = result.get("rows")
    if (
        result.get("schemaVersion") != CONTRACT_VERSION
        or result.get("caseId") != CASE_ID
        or result.get("action") != action
        or result.get("fixtureRef") != state.get("fixtureRef")
        or result.get("hashes") != expected_hashes
        or not isinstance(rows, dict)
        or set(rows) != {"conversation", "message", "user"}
        or any(isinstance(value, bool) or value not in {0, 1} for value in rows.values())
    ):
        raise ValueError("operation_failed")
    expected_count = 0 if action == "destroy" else 1
    if action in {"provision", "destroy"} and any(
        value != expected_count for value in rows.values()
    ):
        raise ValueError("operation_failed")
    return result


def _validate_control_row(
    row: object, state: dict[str, object], *, boundary: str | None
) -> dict[str, object]:
    if not isinstance(row, dict):
        raise ValueError("operation_failed")  # noqa: TRY004
    row_state = row.get("state")
    expected_fields = {
        "armedAt",
        "audit",
        "boundary",
        "controlId",
        "conversationScopeHash",
        "expiresAt",
        "ownerScopeHash",
        "parentScopeHash",
        "purgeAt",
        "state",
        "syntheticScope",
    }
    if row_state == "consumed":
        expected_fields.add("consumedAt")
    elif row_state == "cleared":
        expected_fields.add("clearedAt")
    if set(row) != expected_fields or not set(row).issubset(CONTROL_ROW_FIELDS):
        raise ValueError("operation_failed")
    if (
        not CONTROL_ID_PATTERN.fullmatch(str(row.get("controlId") or ""))
        or row.get("boundary") not in BOUNDARIES
        or (boundary is not None and row.get("boundary") != boundary)
        or row.get("ownerScopeHash") != state.get("ownerScopeHash")
        or row.get("conversationScopeHash") != state.get("conversationScopeHash")
        or row.get("parentScopeHash") != state.get("parentScopeHash")
        or row_state not in CONTROL_STATES
        or row.get("syntheticScope") is not True
    ):
        raise ValueError("operation_failed")
    armed_at = _parse_time(row["armedAt"])
    expires_at = _parse_time(row["expiresAt"])
    purge_at = _parse_time(row["purgeAt"])
    audit = row.get("audit")
    if not armed_at < expires_at < purge_at or not isinstance(audit, list):
        raise ValueError("operation_failed")
    expected_audit_length = 1 if row_state == "armed" else 2
    if len(audit) != expected_audit_length:
        raise ValueError("operation_failed")
    for index, event in enumerate(audit, start=1):
        if not isinstance(event, dict) or set(event) != {"at", "event", "sequence"}:
            raise ValueError("operation_failed")
        if event.get("sequence") != index:
            raise ValueError("operation_failed")
        _parse_time(event.get("at"))
    if audit[0] != {"at": row["armedAt"], "event": "armed", "sequence": 1}:
        raise ValueError("operation_failed")
    if row_state != "armed":
        transition = audit[1]
        if transition.get("event") != row_state:
            raise ValueError("operation_failed")
        transition_at = _parse_time(transition.get("at"))
        if row_state in {"consumed", "cleared"}:
            field = "consumedAt" if row_state == "consumed" else "clearedAt"
            if row.get(field) != transition.get("at") or not armed_at <= transition_at < expires_at:
                raise ValueError("operation_failed")
        elif transition_at < expires_at:
            raise ValueError("operation_failed")
    return row


def _invoke_fixture(
    *,
    action: str,
    state: dict[str, object],
    session: dict[str, object],
    installed_root: Path,
    runtime_env_path: Path,
    runner: RunPrivateJson,
) -> dict[str, object]:
    librechat = _librechat_root(installed_root)
    result = runner(
        argv=[
            _node_binary(),
            str(Path(__file__).with_name("librechat_emo_qa_fixture.js")),
            action,
            "--json",
        ],
        cwd=librechat,
        env=_runner_environment(
            runtime_env_path=runtime_env_path,
            installed_root=installed_root,
            session=None,
            component_artifact_digest=str(state["componentArtifactDigest"]),
        ),
        document=_fixture_document(state),
        private_values=_private_values(state, session),
        fixture=state,
        private_fd=True,
    )
    return _validate_fixture_receipt(result, state, action=action)


def _invoke_control(
    *,
    action: str,
    state: dict[str, object],
    session: dict[str, object],
    installed_root: Path,
    runtime_env_path: Path,
    runner: RunPrivateJson,
    boundary: str | None = None,
    ttl_seconds: int | None = None,
) -> object:
    result = runner(
        argv=[_node_binary(), str(_control_script(installed_root)), action, "--json"],
        cwd=_librechat_root(installed_root),
        env=_runner_environment(
            runtime_env_path=runtime_env_path,
            installed_root=installed_root,
            session=session,
            component_artifact_digest=str(session["componentArtifactDigest"]),
        ),
        document=_scope_document(state, boundary=boundary, ttl_seconds=ttl_seconds),
        private_values=_private_values(state, session),
        fixture=state,
        private_fd=True,
    )
    if action == "arm":
        return _validate_control_row(result, state, boundary=boundary)
    if action == "query":
        if not isinstance(result, list):
            raise ValueError("operation_failed")
        rows = [_validate_control_row(row, state, boundary=boundary) for row in result]
        control_ids = [str(row["controlId"]) for row in rows]
        if len(control_ids) != len(set(control_ids)):
            raise ValueError("operation_failed")
        return rows
    if not isinstance(result, dict) or set(result) != {"cleared"}:
        raise ValueError("operation_failed")
    cleared = result.get("cleared")
    if isinstance(cleared, bool) or not isinstance(cleared, int) or cleared < 0:
        raise ValueError("operation_failed")
    return result


def prepare_fixture(
    *,
    parent_state_path: Path,
    session_state_path: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    local_qa_request_path: Path,
    runtime_env_path: Path,
    now: datetime | None = None,
    random_bytes: Callable[[int], bytes] = secrets.token_bytes,
    runner: RunPrivateJson = _run_private_json,
) -> dict[str, object]:
    checked_at = (now or _utc_now()).astimezone(timezone.utc)
    session = _active_session(
        session_state_path=session_state_path,
        installed_root=installed_root,
        artifact_identity_path=artifact_identity_path,
        local_qa_request_path=local_qa_request_path,
        now=checked_at,
    )
    if parent_state_path.exists() or parent_state_path.is_symlink():
        state = _read_parent_state(parent_state_path)
        _match_parent_to_session(state, session, require_artifact=True)
    else:
        owner_bytes = random_bytes(12)
        namespace_bytes = random_bytes(16)
        if len(owner_bytes) != 12 or len(namespace_bytes) != 16:
            raise ValueError("operation_failed")
        owner_id = owner_bytes.hex()
        namespace = namespace_bytes.hex()
        conversation_id = f"emo_uc_048_conversation_{namespace}"
        parent_id = f"emo_uc_048_parent_{namespace}"
        token_hash = _sha256("case-token", str(session["caseToken"]))
        fixture_ref = "emo048_fixture_" + hashlib.sha256(
            f"{session['sessionRef']}\0{owner_id}\0{namespace}".encode()
        ).hexdigest()[:24]
        state = {
            "artifactIdentityDigest": session["artifactIdentityDigest"],
            "caseId": CASE_ID,
            "caseTokenHash": token_hash,
            "componentArtifactDigest": session["componentArtifactDigest"],
            "contractVersion": CONTRACT_VERSION,
            "conversationId": conversation_id,
            "conversationScopeHash": _sha256("conversation", conversation_id),
            "email": f"emo-uc-048-{namespace}@local-qa.invalid",
            "expiresAt": session["expiresAt"],
            "fixtureRef": fixture_ref,
            "installedRootHash": session["installedRootHash"],
            "ownerId": owner_id,
            "ownerScopeHash": _sha256("owner", owner_id),
            "parentMessageId": parent_id,
            "parentScopeHash": _sha256("parent", parent_id),
            "phase": "provisioning",
            "preparedAt": None,
            "sessionRef": session["sessionRef"],
        }
        _session_module()._write_private_json(parent_state_path, state)
    _invoke_fixture(
        action="provision",
        state=state,
        session=session,
        installed_root=installed_root,
        runtime_env_path=runtime_env_path,
        runner=runner,
    )
    state["phase"] = "prepared"
    state["preparedAt"] = _session_module()._iso(checked_at)
    _session_module()._write_private_json(parent_state_path, state)
    return _redacted_fixture(state)


def arm_fault(
    *,
    parent_state_path: Path,
    session_state_path: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    local_qa_request_path: Path,
    runtime_env_path: Path,
    boundary: str,
    ttl_seconds: int,
    now: datetime | None = None,
    runner: RunPrivateJson = _run_private_json,
) -> dict[str, object]:
    if (
        boundary not in BOUNDARIES
        or isinstance(ttl_seconds, bool)
        or not isinstance(ttl_seconds, int)
    ):
        raise ValueError("EMO-UC-048 boundary or expiry is invalid")
    checked_at = (now or _utc_now()).astimezone(timezone.utc)
    session = _active_session(
        session_state_path=session_state_path,
        installed_root=installed_root,
        artifact_identity_path=artifact_identity_path,
        local_qa_request_path=local_qa_request_path,
        now=checked_at,
    )
    state = _read_parent_state(parent_state_path)
    _match_parent_to_session(state, session, require_artifact=True)
    remaining = int((_parse_time(session["expiresAt"]) - checked_at).total_seconds())
    if state.get("phase") != "prepared" or ttl_seconds < 1 or ttl_seconds > min(3600, remaining):
        raise ValueError("EMO-UC-048 control expiry exceeds the active session")
    existing = _invoke_control(
        action="query",
        state=state,
        session=session,
        installed_root=installed_root,
        runtime_env_path=runtime_env_path,
        runner=runner,
        boundary=boundary,
    )
    if existing:
        if len(existing) != 1:
            raise ValueError("operation_failed")
        existing_duration = _parse_time(existing[0]["expiresAt"]) - _parse_time(
            existing[0]["armedAt"]
        )
        existing_ttl = int(existing_duration.total_seconds())
        if existing_ttl != ttl_seconds:
            raise ValueError("EMO-UC-048 boundary was already armed with a different expiry")
        return {
            "caseId": CASE_ID,
            "fixtureRef": state["fixtureRef"],
            "sessionRef": state["sessionRef"],
            **existing[0],
        }
    row = _invoke_control(
        action="arm",
        state=state,
        session=session,
        installed_root=installed_root,
        runtime_env_path=runtime_env_path,
        runner=runner,
        boundary=boundary,
        ttl_seconds=ttl_seconds,
    )
    return {
        "caseId": CASE_ID,
        "fixtureRef": state["fixtureRef"],
        "sessionRef": state["sessionRef"],
        **row,
    }


def query_faults(
    *,
    parent_state_path: Path,
    session_state_path: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    local_qa_request_path: Path,
    runtime_env_path: Path,
    boundary: str | None,
    runner: RunPrivateJson = _run_private_json,
) -> dict[str, object]:
    del artifact_identity_path, local_qa_request_path
    if boundary is not None and boundary not in BOUNDARIES:
        raise ValueError("EMO-UC-048 boundary is invalid")
    session = _raw_session(session_state_path=session_state_path, installed_root=installed_root)
    state = _read_parent_state(parent_state_path)
    _match_parent_to_session(state, session, require_artifact=False)
    rows = _invoke_control(
        action="query",
        state=state,
        session=session,
        installed_root=installed_root,
        runtime_env_path=runtime_env_path,
        runner=runner,
        boundary=boundary,
    )
    return {
        "caseId": CASE_ID,
        "controls": rows,
        "fixtureRef": state["fixtureRef"],
        "sessionRef": state["sessionRef"],
    }


def clear_faults(
    *,
    parent_state_path: Path,
    session_state_path: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    local_qa_request_path: Path,
    runtime_env_path: Path,
    boundary: str | None,
    runner: RunPrivateJson = _run_private_json,
) -> dict[str, object]:
    del artifact_identity_path, local_qa_request_path
    if boundary is not None and boundary not in BOUNDARIES:
        raise ValueError("EMO-UC-048 boundary is invalid")
    session = _raw_session(session_state_path=session_state_path, installed_root=installed_root)
    state = _read_parent_state(parent_state_path)
    _match_parent_to_session(state, session, require_artifact=False)
    result = _invoke_control(
        action="clear",
        state=state,
        session=session,
        installed_root=installed_root,
        runtime_env_path=runtime_env_path,
        runner=runner,
        boundary=boundary,
    )
    return {
        "caseId": CASE_ID,
        "cleared": result["cleared"],
        "fixtureRef": state["fixtureRef"],
        "sessionRef": state["sessionRef"],
    }


def cleanup_fixture(
    *,
    parent_state_path: Path,
    session_state_path: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    local_qa_request_path: Path,
    runtime_env_path: Path,
    runner: RunPrivateJson = _run_private_json,
) -> dict[str, object]:
    del artifact_identity_path, local_qa_request_path
    session = _raw_session(session_state_path=session_state_path, installed_root=installed_root)
    if not parent_state_path.exists() and not parent_state_path.is_symlink():
        return {"caseId": CASE_ID, "cleaned": False, "sessionRef": session["sessionRef"]}
    state = _read_parent_state(parent_state_path)
    _match_parent_to_session(state, session, require_artifact=False)
    _invoke_control(
        action="clear",
        state=state,
        session=session,
        installed_root=installed_root,
        runtime_env_path=runtime_env_path,
        runner=runner,
    )
    rows = _invoke_control(
        action="query",
        state=state,
        session=session,
        installed_root=installed_root,
        runtime_env_path=runtime_env_path,
        runner=runner,
    )
    if any(row.get("state") == "armed" for row in rows):
        raise ValueError("EMO-UC-048 controls are not clear")
    _invoke_fixture(
        action="destroy",
        state=state,
        session=session,
        installed_root=installed_root,
        runtime_env_path=runtime_env_path,
        runner=runner,
    )
    _read_parent_state(parent_state_path)
    parent_state_path.unlink()
    return {"caseId": CASE_ID, "cleaned": True, "sessionRef": state["sessionRef"]}


def session_clearable(
    *,
    parent_state_path: Path,
    session_state_path: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    local_qa_request_path: Path,
    runtime_env_path: Path,
) -> dict[str, object]:
    del artifact_identity_path, local_qa_request_path, runtime_env_path
    session = _session_module()._read_state(session_state_path)
    if session.get("caseId") != CASE_ID:
        return {"caseId": str(session.get("caseId") or ""), "clearable": True}
    if session.get("installedRootHash") != _session_module()._root_hash(installed_root):
        raise ValueError("local-QA session belongs to a different installed candidate")
    if parent_state_path.exists() or parent_state_path.is_symlink():
        state = _read_parent_state(parent_state_path)
        _match_parent_to_session(state, session, require_artifact=False)
        return {"caseId": CASE_ID, "clearable": False}
    return {"caseId": CASE_ID, "clearable": True}


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--parent-state", type=Path, required=True)
    parser.add_argument("--session-state", type=Path, required=True)
    parser.add_argument("--installed-root", type=Path, required=True)
    parser.add_argument("--artifact-identity", type=Path, required=True)
    parser.add_argument("--local-qa-request", type=Path, required=True)
    parser.add_argument("--runtime-env", type=Path, required=True)


def main(argv: Iterable[str] | None = None) -> int:
    parser = PrivateArgumentParser(description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "query", "clear", "cleanup", "clear-gate"):
        command = commands.add_parser(name, allow_abbrev=False)
        _common(command)
        if name in {"query", "clear"}:
            command.add_argument("--boundary", choices=BOUNDARIES)
    arm = commands.add_parser("arm", allow_abbrev=False)
    _common(arm)
    arm.add_argument("--boundary", choices=BOUNDARIES, required=True)
    arm.add_argument("--ttl-seconds", type=int, default=60)
    values = list(argv) if argv is not None else sys.argv[1:]
    try:
        _reject_duplicate_options(values)
        args = parser.parse_args(values)
    except ValueError:
        print(json.dumps({"caseId": CASE_ID, "error": "operation_failed"}), file=sys.stderr)
        return 2
    common = {
        "parent_state_path": args.parent_state,
        "session_state_path": args.session_state,
        "installed_root": args.installed_root,
        "artifact_identity_path": args.artifact_identity,
        "local_qa_request_path": args.local_qa_request,
        "runtime_env_path": args.runtime_env,
    }
    try:
        if args.command in {"prepare", "arm"}:
            _session_module().require_restart_ready(
                state_path=args.session_state,
                installed_root=args.installed_root,
                artifact_identity_path=args.artifact_identity,
                local_qa_request_path=args.local_qa_request,
            )
        if args.command == "prepare":
            result = prepare_fixture(**common)
        elif args.command == "arm":
            result = arm_fault(
                **common,
                boundary=args.boundary,
                ttl_seconds=args.ttl_seconds,
            )
        elif args.command == "query":
            result = query_faults(**common, boundary=args.boundary)
        elif args.command == "clear":
            result = clear_faults(**common, boundary=args.boundary)
        elif args.command == "cleanup":
            result = cleanup_fixture(**common)
        else:
            result = session_clearable(**common)
            if result["clearable"] is not True:
                raise ValueError("operation_failed")
    except (OSError, RuntimeError, ValueError):
        print(json.dumps({"caseId": CASE_ID, "error": "operation_failed"}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
