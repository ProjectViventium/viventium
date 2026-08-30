#!/usr/bin/env python3
"""Run the private MPV-061 parent arm, approval, receipt, and cleanup control."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path

CASE_ID = "MPV-061"
MODE = "mpv_061"
MAX_SCOPE_BYTES = 16 * 1024
MAX_CHILD_OUTPUT_BYTES = 64 * 1024
HASH = re.compile(r"^sha256:[a-f0-9]{64}$")
TOKEN = re.compile(r"^[A-Za-z0-9_-]{43}$")
CONTROL_ID = re.compile(r"^mpv061_[A-Za-z0-9_-]{22,80}$")
CHALLENGE_ID = re.compile(r"^mpv061_ch_[A-Za-z0-9_-]{22,80}$")
PROOF = re.compile(r"^[A-Za-z0-9_-]{43}$")
OBJECT_ID = re.compile(r"^[a-f0-9]{24}$")
SYNTHETIC_EMAIL = re.compile(
    r"^viventium-voice-qa-mpv-061-[a-z0-9-]{1,80}@example\.com$"
)
SCOPE_FIELDS = {
    "schemaVersion",
    "caseId",
    "candidateDigest",
    "installedArtifactDigest",
    "runtimeOwnerBindingHash",
    "ownerId",
    "ownerEmail",
    "callSessionId",
    "primary",
    "fallback",
}
ROUTE_FIELDS = {"provider", "model"}
SEGMENT_FIELDS = {"segmentId", "revision"}


class DuplicateJsonKeyError(ValueError):
    pass


class PrivateArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise ValueError("operation_failed")


def _load_runtime_control():
    path = Path(__file__).with_name("local_qa_runtime_control.py")
    spec = importlib.util.spec_from_file_location("mpv_061_runtime_control", path)
    if spec is None or spec.loader is None:
        raise ValueError("local-QA runtime control is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    return module


runtime_control = _load_runtime_control()


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError("duplicate JSON key")
        result[key] = value
    return result


def _loads(value: str) -> object:
    return json.loads(value, object_pairs_hook=_unique_object)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _bounded(value: object, label: str) -> str:
    selected = str(value or "").strip()
    if not selected or len(selected) > 256 or "\0" in selected:
        raise ValueError(f"{label} is invalid")
    return selected


def _exact_hash(value: object, label: str) -> str:
    selected = str(value or "").strip()
    if not HASH.fullmatch(selected):
        raise ValueError(f"{label} is invalid")
    return selected


def _route(value: object, label: str) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != ROUTE_FIELDS:
        raise ValueError(f"{label} is invalid")
    return {
        "provider": _bounded(value.get("provider"), label),
        "model": _bounded(value.get("model"), label),
    }


def _decode_token(value: object) -> bytes:
    token = str(value or "")
    if not TOKEN.fullmatch(token):
        raise ValueError("case token is invalid")
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


def _parse_time(value: object) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("challenge timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("challenge timestamp is invalid")
    return parsed.astimezone(timezone.utc)


def validate_scope(
    scope: Mapping[str, object], session: Mapping[str, object]
) -> dict[str, object]:
    if (
        not isinstance(scope, dict)
        or set(scope) != SCOPE_FIELDS
        or scope.get("schemaVersion") != 1
        or scope.get("caseId") != CASE_ID
        or session.get("caseId") != CASE_ID
        or session.get("mode") != MODE
        or session.get("modeVariable") != "VIVENTIUM_LOCAL_QA_MODE"
    ):
        raise ValueError("MPV-061 scope is invalid")
    owner_email = str(scope.get("ownerEmail") or "").strip().lower()
    owner_id = str(scope.get("ownerId") or "").strip().lower()
    if not SYNTHETIC_EMAIL.fullmatch(owner_email) or not OBJECT_ID.fullmatch(owner_id):
        raise ValueError("MPV-061 synthetic owner is invalid")
    candidate = _exact_hash(scope.get("candidateDigest"), "candidate digest")
    if candidate != session.get("artifactIdentityDigest"):
        raise ValueError("MPV-061 candidate binding is invalid")
    primary = _route(scope.get("primary"), "primary route")
    fallback = _route(scope.get("fallback"), "fallback route")
    if primary == fallback:
        raise ValueError("MPV-061 fallback route is invalid")
    _decode_token(session.get("caseToken"))
    return {
        "caseId": CASE_ID,
        "sessionRef": _bounded(session.get("sessionRef"), "session reference"),
        "candidateDigest": candidate,
        "componentArtifactDigest": _exact_hash(
            session.get("componentArtifactDigest"), "component digest"
        ),
        "installedArtifactDigest": _exact_hash(
            scope.get("installedArtifactDigest"), "installed artifact digest"
        ),
        "runtimeOwnerBindingHash": _exact_hash(
            scope.get("runtimeOwnerBindingHash"), "runtime owner binding"
        ),
        "ownerId": owner_id,
        "callSessionId": _bounded(scope.get("callSessionId"), "call session"),
        "primary": primary,
        "fallback": fallback,
    }


def _arm_identity(
    binding: Mapping[str, object], session: Mapping[str, object]
) -> dict[str, object]:
    identity = {
        "schemaVersion": 1,
        "caseId": CASE_ID,
        "sessionRefHash": _sha("session\0" + str(binding["sessionRef"])),
        "sessionCandidateDigest": str(binding["candidateDigest"]),
        "caseTokenHash": _sha("case-token\0" + str(session["caseToken"])),
        "candidateDigest": str(binding["candidateDigest"]),
        "componentArtifactDigest": str(binding["componentArtifactDigest"]),
        "installedArtifactDigest": str(binding["installedArtifactDigest"]),
        "runtimeOwnerBindingHash": str(binding["runtimeOwnerBindingHash"]),
        "ownerScopeHash": _sha("owner\0" + str(binding["ownerId"])),
        "callScopeHash": _sha("call\0" + str(binding["callSessionId"])),
        "primaryProvider": str(binding["primary"]["provider"]),
        "primaryModel": str(binding["primary"]["model"]),
        "fallbackProvider": str(binding["fallback"]["provider"]),
        "fallbackModel": str(binding["fallback"]["model"]),
    }
    return {**identity, "armBindingHash": _sha(_canonical(identity))}


def _segments(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list) or not 1 <= len(value) <= 32:
        raise ValueError("challenge segments are invalid")
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != SEGMENT_FIELDS:
            raise ValueError("challenge segments are invalid")
        segment_id = _bounded(item.get("segmentId"), "challenge segment")
        revision = item.get("revision")
        if type(revision) is not int or revision < 1 or segment_id in seen:
            raise ValueError("challenge segments are invalid")
        seen.add(segment_id)
        result.append({"segmentId": segment_id, "revision": revision})
    return result


def _challenge_unsigned(challenge: Mapping[str, object]) -> dict[str, object]:
    keys = (
        "schemaVersion",
        "caseId",
        "controlId",
        "challengeId",
        "challengeIssuedAt",
        "challengeExpiresAt",
        "replayExpiresAt",
        "sessionRefHash",
        "sessionCandidateDigest",
        "candidateDigest",
        "componentArtifactDigest",
        "installedArtifactDigest",
        "runtimeOwnerBindingHash",
        "ownerScopeHash",
        "callScopeHash",
        "turnId",
        "segments",
        "turnScopeHash",
        "segmentSetHash",
        "utteranceHash",
        "primaryProvider",
        "primaryModel",
        "fallbackProvider",
        "fallbackModel",
    )
    return {key: challenge.get(key) for key in keys}


def verify_challenge(
    challenge: Mapping[str, object],
    *,
    scope: Mapping[str, object],
    session: Mapping[str, object],
    now: datetime | None = None,
) -> dict[str, object]:
    binding = validate_scope(scope, session)
    arm = _arm_identity(binding, session)
    segments = _segments(challenge.get("segments"))
    turn_id = _bounded(challenge.get("turnId"), "challenge turn")
    utterance_hash = _exact_hash(challenge.get("utteranceHash"), "challenge utterance")
    turn = {
        "armBindingHash": arm["armBindingHash"],
        "turnScopeHash": _sha("turn\0" + turn_id),
        "segmentSetHash": _sha(_canonical(segments)),
        "utteranceHash": utterance_hash,
    }
    expected = {
        "schemaVersion": 1,
        "caseId": CASE_ID,
        "sessionRefHash": arm["sessionRefHash"],
        "sessionCandidateDigest": binding["candidateDigest"],
        "candidateDigest": binding["candidateDigest"],
        "componentArtifactDigest": binding["componentArtifactDigest"],
        "installedArtifactDigest": binding["installedArtifactDigest"],
        "runtimeOwnerBindingHash": binding["runtimeOwnerBindingHash"],
        "ownerScopeHash": arm["ownerScopeHash"],
        "callScopeHash": arm["callScopeHash"],
        "armBindingHash": arm["armBindingHash"],
        "turnScopeHash": turn["turnScopeHash"],
        "segmentSetHash": turn["segmentSetHash"],
        "turnBindingHash": _sha(_canonical(turn)),
        "primaryProvider": binding["primary"]["provider"],
        "primaryModel": binding["primary"]["model"],
        "fallbackProvider": binding["fallback"]["provider"],
        "fallbackModel": binding["fallback"]["model"],
    }
    if any(challenge.get(key) != value for key, value in expected.items()):
        raise ValueError("MPV-061 challenge binding is invalid")
    if (
        challenge.get("state") != "challenged"
        or not CONTROL_ID.fullmatch(str(challenge.get("controlId") or ""))
        or not CHALLENGE_ID.fullmatch(str(challenge.get("challengeId") or ""))
        or not PROOF.fullmatch(str(challenge.get("coreProof") or ""))
    ):
        raise ValueError("MPV-061 challenge authority is invalid")
    checked_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    issued_at = _parse_time(challenge.get("challengeIssuedAt"))
    expires_at = _parse_time(challenge.get("challengeExpiresAt"))
    replay_expires_at = _parse_time(challenge.get("replayExpiresAt"))
    if not issued_at <= checked_at < expires_at <= issued_at + timedelta(seconds=5):
        raise ValueError("MPV-061 challenge is stale")
    if replay_expires_at != issued_at + timedelta(seconds=60):
        raise ValueError("MPV-061 challenge replay window is invalid")
    approval_payload = str(challenge.get("approvalPayload") or "")
    try:
        parsed_payload = _loads(approval_payload)
    except (ValueError, json.JSONDecodeError, DuplicateJsonKeyError) as exc:
        raise ValueError("MPV-061 challenge approval payload is invalid") from exc
    expected_payload = {
        **_challenge_unsigned(challenge),
        "coreProof": challenge["coreProof"],
    }
    if parsed_payload != expected_payload or approval_payload != _canonical(
        expected_payload
    ):
        raise ValueError("MPV-061 challenge approval payload is invalid")
    return {
        **binding,
        "turnId": turn_id,
        "segments": segments,
        "utteranceHash": utterance_hash,
    }


def _approval_proof(payload: str, token: object) -> str:
    digest = hmac.new(
        _decode_token(token), payload.encode("utf-8"), hashlib.sha256
    ).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def run_parent_control(
    *,
    scope: Mapping[str, object],
    session: Mapping[str, object],
    invoke_cli: Callable[[str, Mapping[str, object], float], object],
    emit: Callable[[dict[str, object]], None],
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, object]:
    binding = validate_scope(scope, session)
    armed = invoke_cli("arm", {"schemaVersion": 1, "binding": binding}, 10.0)
    if not isinstance(armed, dict) or not CONTROL_ID.fullmatch(
        str(armed.get("controlId") or "")
    ):
        raise ValueError("MPV-061 arm failed")
    emit({"event": "armed", "caseId": CASE_ID, "controlId": armed["controlId"]})
    challenge = invoke_cli(
        "watch", {"schemaVersion": 1, "controlId": armed["controlId"]}, 65.0
    )
    if (
        not isinstance(challenge, dict)
        or challenge.get("controlId") != armed["controlId"]
    ):
        raise ValueError("MPV-061 challenge is unavailable")
    turn_binding = verify_challenge(challenge, scope=scope, session=session)
    approval_started = monotonic()
    proof = _approval_proof(str(challenge["approvalPayload"]), session.get("caseToken"))
    approved = invoke_cli(
        "approve",
        {
            "schemaVersion": 1,
            "controlId": challenge["controlId"],
            "challengeId": challenge["challengeId"],
            "binding": turn_binding,
            "approvalProof": proof,
        },
        0.70,
    )
    if (
        monotonic() - approval_started > 0.70
        or not isinstance(approved, dict)
        or approved.get("approved") is not True
    ):
        raise ValueError("MPV-061 parent approval missed its deadline")
    receipt = invoke_cli(
        "receipt", {"schemaVersion": 1, "controlId": challenge["controlId"]}, 15.0
    )
    if (
        not isinstance(receipt, dict)
        or receipt.get("state") != "consumed"
        or receipt.get("controlId") != challenge["controlId"]
        or not HASH.fullmatch(str(receipt.get("receiptDigest") or ""))
    ):
        raise ValueError("MPV-061 receipt is unavailable")
    result = {
        "event": "receipt",
        "caseId": CASE_ID,
        "controlId": receipt["controlId"],
        "receiptDigest": receipt["receiptDigest"],
        "receiptExpiresAt": receipt.get("receiptExpiresAt"),
    }
    emit(result)
    return result


def cleanup_parent_control(
    scope: Mapping[str, object],
    *,
    session: Mapping[str, object],
    invoke_cli: Callable[[str, Mapping[str, object], float], object],
) -> dict[str, int]:
    if (
        not isinstance(scope, dict)
        or set(scope) != {"schemaVersion", "caseId", "controlId", "receiptDigest"}
        or scope.get("schemaVersion") != 1
        or scope.get("caseId") != CASE_ID
        or session.get("caseId") != CASE_ID
        or not CONTROL_ID.fullmatch(str(scope.get("controlId") or ""))
        or not HASH.fullmatch(str(scope.get("receiptDigest") or ""))
    ):
        raise ValueError("MPV-061 cleanup scope is invalid")
    result = invoke_cli(
        "cleanup",
        {
            "schemaVersion": 1,
            "controlId": scope["controlId"],
            "receiptDigest": scope["receiptDigest"],
        },
        10.0,
    )
    if not isinstance(result, dict) or result.get("removed") != 1:
        raise ValueError("MPV-061 cleanup did not remove one exact receipt")
    return {"removed": 1}


def cli_invocation(
    command: str,
    scope_fd: int,
    session: Mapping[str, object],
    *,
    environ: Mapping[str, str] | None = None,
) -> tuple[list[str], dict[str, str]]:
    selected = dict(os.environ if environ is None else environ)
    node = shutil.which("node", path=selected.get("PATH"))
    script = (
        Path(__file__).resolve().parents[2]
        / "viventium_v0_4"
        / "LibreChat"
        / "scripts"
        / "viventium-voice-classifier-fault-control.js"
    )
    if not node or not script.is_file():
        raise ValueError("MPV-061 Core control CLI is unavailable")
    selected.update(
        {
            "VIVENTIUM_LOCAL_QA_CASE_ID": CASE_ID,
            "VIVENTIUM_LOCAL_QA_MODE": MODE,
            "VIVENTIUM_LOCAL_QA_CASE_TOKEN": str(session["caseToken"]),
            "VIVENTIUM_LOCAL_QA_SESSION_REF": str(session["sessionRef"]),
            "VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST": str(
                session["componentArtifactDigest"]
            ),
            "VIVENTIUM_LOCAL_QA_CANDIDATE_DIGEST": str(
                session["artifactIdentityDigest"]
            ),
        }
    )
    return [node, str(script), command, "--scope-fd", str(scope_fd)], selected


def invoke_cli_private(
    command: str,
    payload: Mapping[str, object],
    timeout_seconds: float,
    *,
    session: Mapping[str, object],
) -> object:
    descriptor, path = tempfile.mkstemp(prefix="mpv061-control-")
    try:
        os.fchmod(descriptor, 0o600)
        os.write(descriptor, _canonical(dict(payload)).encode("utf-8"))
        os.lseek(descriptor, 0, os.SEEK_SET)
        os.unlink(path)
        args, child_env = cli_invocation(command, descriptor, session)
        completed = subprocess.run(
            args,
            env=child_env,
            pass_fds=(descriptor,),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if (
            completed.returncode != 0
            or len(completed.stdout.encode()) > MAX_CHILD_OUTPUT_BYTES
        ):
            raise ValueError("MPV-061 Core control CLI failed")
        result = _loads(completed.stdout)
        if not isinstance(result, dict):
            raise TypeError("MPV-061 Core control CLI returned invalid data")
        return result
    finally:
        os.close(descriptor)
        if os.path.exists(path):
            os.unlink(path)


def _read_private_scope(descriptor: int) -> dict[str, object]:
    metadata = os.fstat(descriptor)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_nlink != 1
        or not 1 <= metadata.st_size <= MAX_SCOPE_BYTES
    ):
        raise ValueError("MPV-061 private scope is invalid")
    raw = os.read(descriptor, MAX_SCOPE_BYTES + 1)
    after = os.fstat(descriptor)
    if len(raw) != metadata.st_size or metadata.st_ino != after.st_ino:
        raise ValueError("MPV-061 private scope changed")
    try:
        value = _loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("MPV-061 private scope is invalid") from exc
    if not isinstance(value, dict):
        raise TypeError("MPV-061 private scope is invalid")
    return value


def _runtime_paths(environ: Mapping[str, str]) -> dict[str, Path]:
    support = Path(str(environ.get("VIVENTIUM_APP_SUPPORT_DIR") or "")).expanduser()
    if not support.is_absolute():
        raise ValueError("MPV-061 runtime path is unavailable")
    runtime = support.resolve(strict=True) / "runtime"
    return {
        "state": (runtime / "local-qa" / "active.json").resolve(strict=True),
        "installed_root": Path(__file__).resolve(strict=True).parents[2],
        "artifact_identity": (runtime / "parallel-work-artifact-identity.json").resolve(
            strict=True
        ),
        "local_qa_request": (runtime / "parallel-work-local-qa-request.json").resolve(
            strict=True
        ),
    }


def _active_ready_session(environ: Mapping[str, str]) -> dict[str, object]:
    paths = _runtime_paths(environ)
    session = runtime_control.active_session(**paths)
    ready = runtime_control.require_restart_ready(**paths)
    if ready.get("caseId") != CASE_ID or session.get("caseId") != CASE_ID:
        raise ValueError("MPV-061 local-QA session is not active")
    return session


def main(argv: Iterable[str] | None = None) -> int:
    parser = PrivateArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("command", choices=("serve", "cleanup"))
    parser.add_argument("--scope-fd", type=int, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.scope_fd < 3 or args.scope_fd > 1024:
        raise ValueError("operation_failed")
    scope = _read_private_scope(args.scope_fd)
    session = _active_ready_session(os.environ)
    invoke = lambda command, payload, timeout: invoke_cli_private(
        command, payload, timeout, session=session
    )
    if args.command == "cleanup":
        print(
            json.dumps(
                cleanup_parent_control(scope, session=session, invoke_cli=invoke),
                sort_keys=True,
            )
        )
        return 0
    run_parent_control(
        scope=scope,
        session=session,
        invoke_cli=invoke,
        emit=lambda event: print(json.dumps(event, sort_keys=True), flush=True),
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:  # noqa: BLE001 - fail closed without exposing private QA data
        print(
            json.dumps({"ok": False, "error": "mpv_061_parent_control_failed"}),
            file=sys.stderr,
        )
        raise SystemExit(1)
