"""One-shot installed local-QA timing control for Telegram case TR-026."""

from __future__ import annotations

import argparse
import asyncio
import base64
import binascii
import contextlib
import fcntl
import hashlib
import hmac
import json
import os
import re
import stat
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from pathlib import Path

TR026_CASE_ID = "TR-026"
TR026_LOCAL_QA_MODE = "tr-026"
LOCAL_QA_CASE_ID_ENV = "VIVENTIUM_LOCAL_QA_CASE_ID"
LOCAL_QA_CASE_TOKEN_ENV = "VIVENTIUM_LOCAL_QA_CASE_TOKEN"
LOCAL_QA_SESSION_REF_ENV = "VIVENTIUM_LOCAL_QA_SESSION_REF"
TR026_DELAY_MS = 280
_SCHEMA_VERSION = 2
_AUDIT_SCHEMA_VERSION = 3
_AUDIT_GENESIS_HASH = "0" * 64
_AUDIT_LEDGER_SEMANTICS = "owner_mutable_append_only_tamper_evident"
_ARM_ENVELOPE_SCHEMA_VERSION = 1
_ARM_ENVELOPE_MAX_BYTES = 4096
_ARM_ENVELOPE_FIELDS = {
    "schema_version",
    "case_id",
    "case_token",
    "session_ref",
    "target",
    "ttl_seconds",
}
_ARM_TARGET_FIELDS = {
    "owner_user_id",
    "chat_id",
    "thread_id",
    "stale_source_sequence",
    "source_sequence",
    "update_id",
}
_TOKEN_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_CASE_TOKEN = re.compile(r"^[A-Za-z0-9_-]{43}$")


@dataclass(frozen=True)
class SyntheticTelegramSourceEvent:
    update_id: int
    chat_id: int
    thread_id: int
    source_sequence: int
    owner_user_id: int
    event_kind: str = "telegram_source"


@dataclass(frozen=True)
class ArmReceipt:
    artifact_ref: str
    session_ref: str

    @property
    def case_id(self) -> str:
        return TR026_CASE_ID

    @property
    def delay_ms(self) -> int:
        return TR026_DELAY_MS


@dataclass(frozen=True)
class DelayResult:
    applied: bool
    reason: str
    delay_ms: int = 0
    artifact_ref: str = ""


class TR026ControlError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class _PrivateArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        raise TR026ControlError("invalid_arguments")


def _default_state_dir() -> Path:
    configured = str(os.environ.get("VIVENTIUM_TELEGRAM_STATE_DIR") or "").strip()
    if configured:
        return Path(configured).expanduser()
    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Viventium"
            / "runtime"
            / "telegram"
        )
    state_home = str(os.environ.get("XDG_STATE_HOME") or "").strip()
    if state_home:
        return Path(state_home).expanduser() / "viventium" / "telegram"
    return Path.home() / ".local" / "state" / "viventium" / "telegram"


def _control_root(state_dir: Path | None = None) -> Path:
    return Path(state_dir or _default_state_dir()) / "local-qa" / "tr-026"


def _assert_private_directory(path: Path) -> None:
    if path.is_symlink():
        raise RuntimeError("TR-026 local-QA state directory cannot be a symlink")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir() or path.stat().st_uid != os.getuid():
        raise RuntimeError("TR-026 local-QA state directory is not owner-controlled")
    os.chmod(path, 0o700)


def _ensure_layout(state_dir: Path | None = None) -> Path:
    state_root = Path(state_dir or _default_state_dir())
    local_qa_root = state_root / "local-qa"
    _assert_private_directory(local_qa_root)
    root = local_qa_root / "tr-026"
    _assert_private_directory(root)
    for name in ("armed", "consumed", "rejected", "audit"):
        _assert_private_directory(root / name)
    return root


@contextlib.contextmanager
def _locked(root: Path):
    lock_path = root / ".control.lock"
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(lock_path, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_json(path: Path, payload: dict, *, mode: int) -> None:
    encoded = (
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(temporary, flags, 0o600)
    try:
        view = memoryview(encoded)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("Could not persist TR-026 local-QA artifact")
            view = view[written:]
        os.fsync(descriptor)
    except BaseException:
        os.close(descriptor)
        temporary.unlink(missing_ok=True)
        raise
    else:
        os.close(descriptor)
    os.replace(temporary, path)
    os.chmod(path, mode)
    _fsync_directory(path.parent)


def _token_digest(case_token: str) -> str:
    return hashlib.sha256(str(case_token).encode("utf-8")).hexdigest()


def _strict_case_token(case_token: object) -> str:
    token = str(case_token or "")
    try:
        decoded = base64.urlsafe_b64decode(token + "=")
    except (binascii.Error, TypeError, ValueError) as exc:
        raise ValueError("invalid local-QA case token") from exc
    if (
        not _CASE_TOKEN.fullmatch(token)
        or len(decoded) != 32
        or base64.urlsafe_b64encode(decoded).decode().rstrip("=") != token
    ):
        raise ValueError("invalid TR-026 case token")
    return token


def _strict_case_id(case_id: object) -> str:
    if str(case_id or "") != TR026_CASE_ID:
        raise ValueError("TR-026 requires the canonical case ID")
    return TR026_CASE_ID


def _session_ref_for_digest(token_digest: str) -> str:
    return "qa_" + token_digest[:24]


def _strict_session_ref(case_token: str, session_ref: object) -> str:
    normalized = str(session_ref or "")
    expected = _session_ref_for_digest(_token_digest(case_token))
    if normalized != expected:
        raise ValueError("TR-026 session reference does not match the canonical token")
    return normalized


def _event_digest(event: SyntheticTelegramSourceEvent, token_digest: str) -> str:
    encoded = json.dumps(asdict(event), sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(bytes.fromhex(token_digest), encoded, hashlib.sha256).hexdigest()


def _audit_record_hash(case_token: str, payload: dict) -> str:
    unsigned = {key: value for key, value in payload.items() if key != "record_hash"}
    encoded = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(case_token.encode("utf-8"), encoded, hashlib.sha256).hexdigest()


def _read_case_audit_records(
    root: Path, case_token: str, session_ref: str
) -> list[dict]:
    token = _strict_case_token(case_token)
    normalized_session_ref = _strict_session_ref(token, session_ref)
    artifact_ref = _token_digest(token)[:16]
    audit_dir = root / "audit"
    if not audit_dir.is_dir():
        return []
    records = []
    previous_hash = _AUDIT_GENESIS_HASH
    required_fields = {
        "schema_version",
        "case_id",
        "artifact_ref",
        "session_ref",
        "ledger_semantics",
        "chain_index",
        "previous_record_hash",
        "record_hash",
        "recorded_at_ms",
        "outcome",
        "reason",
        "configured_delay_ms",
        "observed_delay_ms",
        "event_digest",
    }
    for expected_index, path in enumerate(
        sorted(audit_dir.glob(f"{artifact_ref}-*.json")), start=1
    ):
        try:
            if (
                path.is_symlink()
                or not path.is_file()
                or path.stat().st_uid != os.getuid()
                or stat.S_IMODE(path.stat().st_mode) != 0o600
                or path.stat().st_size > 8192
            ):
                raise ValueError
            item = json.loads(path.read_text(encoding="utf-8"))
            if (
                not isinstance(item, dict)
                or set(item) != required_fields
                or item.get("schema_version") != _AUDIT_SCHEMA_VERSION
                or item.get("case_id") != TR026_CASE_ID
                or item.get("artifact_ref") != artifact_ref
                or item.get("session_ref") != normalized_session_ref
                or item.get("ledger_semantics") != _AUDIT_LEDGER_SEMANTICS
                or item.get("chain_index") != expected_index
                or item.get("previous_record_hash") != previous_hash
                or not _TOKEN_DIGEST.fullmatch(str(item.get("record_hash") or ""))
            ):
                raise ValueError
            expected_hash = _audit_record_hash(token, item)
            if not hmac.compare_digest(expected_hash, item["record_hash"]):
                raise ValueError
        except Exception as exc:
            raise ValueError("TR-026 audit ledger integrity check failed") from exc
        records.append(item)
        previous_hash = item["record_hash"]
    return records


def _audit(
    root: Path,
    *,
    case_token: str,
    session_ref: str,
    outcome: str,
    reason: str,
    event_digest: str = "",
    observed_delay_ms: int = 0,
) -> None:
    token = _strict_case_token(case_token)
    normalized_session_ref = _strict_session_ref(token, session_ref)
    existing = _read_case_audit_records(root, token, normalized_session_ref)
    chain_index = len(existing) + 1
    previous_hash = existing[-1]["record_hash"] if existing else _AUDIT_GENESIS_HASH
    artifact_ref = _token_digest(token)[:16]
    payload = {
        "schema_version": _AUDIT_SCHEMA_VERSION,
        "case_id": TR026_CASE_ID,
        "artifact_ref": artifact_ref,
        "session_ref": normalized_session_ref,
        "ledger_semantics": _AUDIT_LEDGER_SEMANTICS,
        "chain_index": chain_index,
        "previous_record_hash": previous_hash,
        "recorded_at_ms": int(time.time() * 1000),
        "outcome": outcome,
        "reason": reason,
        "configured_delay_ms": TR026_DELAY_MS,
        "observed_delay_ms": max(0, int(observed_delay_ms)),
        "event_digest": event_digest,
    }
    payload["record_hash"] = _audit_record_hash(token, payload)
    name = f"{artifact_ref}-{chain_index:08d}-{uuid.uuid4().hex}.json"
    _atomic_json(root / "audit" / name, payload, mode=0o600)


def _strict_positive_int(value, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")  # noqa: TRY004
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _strict_chat_id(value) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("chat_id must be an integer")  # noqa: TRY004
    if value == 0:
        raise ValueError("chat_id must be nonzero")
    return value


def _strict_thread_id(value) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("thread_id must be an integer")  # noqa: TRY004
    if value < 0:
        raise ValueError("thread_id cannot be negative")
    return value


def arm_tr026_control(
    *,
    case_token,
    session_ref,
    owner_user_id,
    chat_id,
    thread_id,
    stale_source_sequence,
    source_sequence,
    update_id,
    case_id=TR026_CASE_ID,
    ttl_seconds: int = 120,
    state_dir: Path | None = None,
) -> ArmReceipt:
    """Create one private, exact, short-lived TR-026 control artifact."""

    normalized_case_id = _strict_case_id(case_id)
    normalized_case_token = _strict_case_token(case_token)
    normalized_session_ref = _strict_session_ref(normalized_case_token, session_ref)
    normalized_owner_user_id = _strict_positive_int(owner_user_id, "owner_user_id")
    normalized_chat_id = _strict_chat_id(chat_id)
    normalized_thread_id = _strict_thread_id(thread_id)
    stale_sequence = _strict_positive_int(
        stale_source_sequence, "stale_source_sequence"
    )
    target_sequence = _strict_positive_int(source_sequence, "source_sequence")
    normalized_update_id = _strict_positive_int(update_id, "update_id")
    ttl = _strict_positive_int(ttl_seconds, "ttl_seconds")
    if target_sequence != stale_sequence + 1:
        raise ValueError("source_sequence must be exactly stale_source_sequence + 1")
    if ttl > 300:
        raise ValueError("ttl_seconds cannot exceed 300")

    root = _ensure_layout(state_dir)
    created_at_ms = int(time.time() * 1000)
    expires_at_ms = created_at_ms + ttl * 1000
    digest = _token_digest(normalized_case_token)
    plan = {
        "schema_version": _SCHEMA_VERSION,
        "case_id": normalized_case_id,
        "local_qa_mode": TR026_LOCAL_QA_MODE,
        "case_token_sha256": digest,
        "session_ref": normalized_session_ref,
        "created_at_ms": created_at_ms,
        "expires_at_ms": expires_at_ms,
        "delay_ms": TR026_DELAY_MS,
        "event": {
            "event_kind": "telegram_source",
            "owner_user_id": normalized_owner_user_id,
            "chat_id": normalized_chat_id,
            "thread_id": normalized_thread_id,
            "stale_source_sequence": stale_sequence,
            "source_sequence": target_sequence,
            "update_id": normalized_update_id,
        },
    }
    with _locked(root):
        if any((root / "armed").glob("*.json")):
            raise TR026ControlError("control_already_armed")
        _atomic_json(root / "armed" / f"{digest}.json", plan, mode=0o600)
    return ArmReceipt(
        artifact_ref=digest[:16],
        session_ref=normalized_session_ref,
    )


def _load_plan(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_uid != os.getuid():
        raise ValueError("unsafe plan file")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError("plan file is not private")
    if path.stat().st_size > 8192:
        raise ValueError("plan file is too large")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {
        "schema_version",
        "case_id",
        "local_qa_mode",
        "case_token_sha256",
        "session_ref",
        "created_at_ms",
        "expires_at_ms",
        "delay_ms",
        "event",
    }:
        raise ValueError("invalid plan fields")
    event = raw.get("event")
    if not isinstance(event, dict) or set(event) != {
        "event_kind",
        "owner_user_id",
        "chat_id",
        "thread_id",
        "stale_source_sequence",
        "source_sequence",
        "update_id",
    }:
        raise ValueError("invalid event fields")
    digest = str(raw.get("case_token_sha256") or "")
    session_ref = str(raw.get("session_ref") or "")
    if (
        raw.get("schema_version") != _SCHEMA_VERSION
        or raw.get("case_id") != TR026_CASE_ID
        or raw.get("local_qa_mode") != TR026_LOCAL_QA_MODE
        or raw.get("delay_ms") != TR026_DELAY_MS
        or not _TOKEN_DIGEST.fullmatch(digest)
        or session_ref != _session_ref_for_digest(digest)
        or path.stem != digest
        or event.get("event_kind") != "telegram_source"
    ):
        raise ValueError("invalid plan contract")
    created_at_ms = _strict_positive_int(raw.get("created_at_ms"), "created_at_ms")
    expires_at_ms = _strict_positive_int(raw.get("expires_at_ms"), "expires_at_ms")
    if expires_at_ms <= created_at_ms or expires_at_ms - created_at_ms > 300_000:
        raise ValueError("invalid plan expiry")
    chat_id = _strict_chat_id(event.get("chat_id"))
    thread_id = _strict_thread_id(event.get("thread_id"))
    owner_user_id = _strict_positive_int(event.get("owner_user_id"), "owner_user_id")
    stale_sequence = _strict_positive_int(
        event.get("stale_source_sequence"), "stale_source_sequence"
    )
    source_sequence = _strict_positive_int(
        event.get("source_sequence"), "source_sequence"
    )
    update_id = _strict_positive_int(event.get("update_id"), "update_id")
    if source_sequence != stale_sequence + 1:
        raise ValueError("invalid source sequence pair")
    raw["created_at_ms"] = created_at_ms
    raw["expires_at_ms"] = expires_at_ms
    raw["event"] = {
        **event,
        "owner_user_id": owner_user_id,
        "chat_id": chat_id,
        "thread_id": thread_id,
        "stale_source_sequence": stale_sequence,
        "source_sequence": source_sequence,
        "update_id": update_id,
    }
    return raw


def _reject(
    root: Path,
    path: Path,
    case_token: str,
    session_ref: str,
    reason: str,
    event_digest: str = "",
) -> None:
    destination = root / "rejected" / path.name
    os.replace(path, destination)
    os.chmod(destination, 0o400)
    _fsync_directory(path.parent)
    _fsync_directory(destination.parent)
    _audit(
        root,
        case_token=case_token,
        session_ref=session_ref,
        outcome="rejected",
        reason=reason,
        event_digest=event_digest,
    )


async def maybe_delay_tr026_core_ingestion(
    event: SyntheticTelegramSourceEvent,
    *,
    state_dir: Path | None = None,
    sleeper: Callable[[float], Awaitable[None]] | None = None,
) -> DelayResult:
    """Atomically consume an exact plan and delay only its Core admission boundary."""

    if os.environ.get("VIVENTIUM_TELEGRAM_LOCAL_QA_MODE") != TR026_LOCAL_QA_MODE:
        return DelayResult(False, "disabled")
    raw_case_id = os.environ.get(LOCAL_QA_CASE_ID_ENV)
    if not raw_case_id:
        return DelayResult(False, "missing_case_id")
    if raw_case_id != TR026_CASE_ID:
        return DelayResult(False, "case_id_mismatch")
    raw_case_token = os.environ.get(LOCAL_QA_CASE_TOKEN_ENV)
    if not raw_case_token:
        return DelayResult(False, "missing_case_token")
    try:
        case_token = _strict_case_token(raw_case_token)
    except ValueError:
        return DelayResult(False, "invalid_case_token")
    raw_session_ref = os.environ.get(LOCAL_QA_SESSION_REF_ENV)
    if not raw_session_ref:
        return DelayResult(False, "missing_session_ref")
    try:
        session_ref = _strict_session_ref(case_token, raw_session_ref)
    except ValueError:
        return DelayResult(False, "session_ref_mismatch")
    if not isinstance(event, SyntheticTelegramSourceEvent):
        return DelayResult(False, "malformed_event")
    try:
        _strict_positive_int(event.update_id, "update_id")
        _strict_chat_id(event.chat_id)
        _strict_thread_id(event.thread_id)
        _strict_positive_int(event.source_sequence, "source_sequence")
        _strict_positive_int(event.owner_user_id, "owner_user_id")
    except ValueError:
        return DelayResult(False, "malformed_event")

    root = _ensure_layout(state_dir)
    runtime_digest = _token_digest(case_token)
    incoming_digest = ""
    claimed_digest = ""
    with _locked(root):
        armed = sorted((root / "armed").glob("*.json"))
        if not armed:
            return DelayResult(False, "not_targeted")
        matching_path = root / "armed" / f"{runtime_digest}.json"
        if matching_path not in armed:
            return DelayResult(False, "case_token_mismatch")
        if len(armed) != 1:
            for path in armed:
                _reject(root, path, case_token, session_ref, "ambiguous_plans")
            return DelayResult(False, "ambiguous_plans")
        path = armed[0]
        try:
            plan = _load_plan(path)
        except (OSError, UnicodeError, ValueError):
            _reject(
                root, path, case_token, session_ref, "malformed_plan", incoming_digest
            )
            return DelayResult(False, "malformed_plan")
        claimed_digest = plan["case_token_sha256"]
        if not hmac.compare_digest(runtime_digest, claimed_digest):
            return DelayResult(False, "case_token_mismatch")
        if plan["case_id"] != raw_case_id:
            return DelayResult(False, "case_id_mismatch")
        if plan["session_ref"] != session_ref:
            return DelayResult(False, "session_ref_mismatch")
        incoming_digest = _event_digest(event, claimed_digest)
        if int(time.time() * 1000) > plan["expires_at_ms"]:
            _reject(root, path, case_token, session_ref, "expired", incoming_digest)
            return DelayResult(False, "expired")
        expected = plan["event"]
        if event.update_id != expected["update_id"]:
            return DelayResult(False, "not_targeted")
        mismatch = ""
        if event.event_kind != expected["event_kind"]:
            mismatch = "wrong_event_kind"
        elif event.owner_user_id != expected["owner_user_id"]:
            mismatch = "cross_owner"
        elif event.chat_id != expected["chat_id"]:
            mismatch = "cross_chat"
        elif event.thread_id != expected["thread_id"]:
            mismatch = "cross_thread"
        elif event.source_sequence != expected["source_sequence"]:
            mismatch = "cross_sequence"
        if mismatch:
            _reject(root, path, case_token, session_ref, mismatch, incoming_digest)
            return DelayResult(False, mismatch)
        consumed = root / "consumed" / path.name
        os.replace(path, consumed)
        os.chmod(consumed, 0o400)
        _fsync_directory(path.parent)
        _fsync_directory(consumed.parent)
        _audit(
            root,
            case_token=case_token,
            session_ref=session_ref,
            outcome="claimed",
            reason="exact_structured_target",
            event_digest=incoming_digest,
        )
        _audit(
            root,
            case_token=case_token,
            session_ref=session_ref,
            outcome="delay_requested",
            reason="core_admission_boundary",
            event_digest=incoming_digest,
        )

    delay = sleeper or asyncio.sleep
    started = time.monotonic()
    try:
        await delay(TR026_DELAY_MS / 1000)
    except BaseException:
        with _locked(root):
            _audit(
                root,
                case_token=case_token,
                session_ref=session_ref,
                outcome="interrupted",
                reason="delay_interrupted_after_atomic_claim",
                event_digest=incoming_digest,
                observed_delay_ms=round((time.monotonic() - started) * 1000),
            )
        raise
    return DelayResult(True, "applied", TR026_DELAY_MS, claimed_digest[:16])


def cleanup_tr026_control(
    *,
    case_token: str,
    session_ref: str,
    case_id: str = TR026_CASE_ID,
    state_dir: Path | None = None,
) -> bool:
    _strict_case_id(case_id)
    case_token = _strict_case_token(case_token)
    session_ref = _strict_session_ref(case_token, session_ref)
    root = _control_root(state_dir)
    if not root.exists():
        return False
    root = _ensure_layout(state_dir)
    digest = _token_digest(case_token)
    removed = False
    with _locked(root):
        for directory in ("armed", "consumed", "rejected"):
            path = root / directory / f"{digest}.json"
            if path.is_file() and not path.is_symlink():
                path.unlink()
                _fsync_directory(path.parent)
                removed = True
        if removed:
            _audit(
                root,
                case_token=case_token,
                session_ref=session_ref,
                outcome="cleaned",
                reason="token_authorized_cleanup",
            )
    return removed


def read_redacted_audit(
    *,
    case_token: str,
    session_ref: str,
    case_id: str = TR026_CASE_ID,
    state_dir: Path | None = None,
) -> list[dict]:
    _strict_case_id(case_id)
    case_token = _strict_case_token(case_token)
    session_ref = _strict_session_ref(case_token, session_ref)
    root = _control_root(state_dir)
    if not (root / "audit").is_dir():
        return []
    return _read_case_audit_records(root, case_token, session_ref)


def _parser() -> argparse.ArgumentParser:
    parser = _PrivateArgumentParser(
        prog="tr026-local-qa",
        description="Manage the one-shot TR-026 local-QA control",
    )
    parser.add_argument("--state-dir", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "arm", help="read one private JSON envelope and arm one exact control"
    )
    cleanup = subparsers.add_parser(
        "cleanup", help="read the case token from stdin and remove its plan"
    )
    cleanup.add_argument("--case-id", required=True, choices=[TR026_CASE_ID])
    cleanup.add_argument("--session-ref", required=True)
    audit = subparsers.add_parser(
        "audit", help="read the case token from stdin and verify redacted evidence"
    )
    audit.add_argument("--case-id", required=True, choices=[TR026_CASE_ID])
    audit.add_argument("--session-ref", required=True)
    return parser


def _read_bounded_private_stdin(
    *, max_bytes: int, missing_code: str, invalid_code: str
) -> str:
    stream = getattr(sys.stdin, "buffer", sys.stdin)
    raw = stream.read(max_bytes + 1)
    if isinstance(raw, str):
        encoded = raw.encode("utf-8")
    else:
        encoded = bytes(raw)
    if len(encoded) > max_bytes:
        raise TR026ControlError(invalid_code)
    try:
        text = encoded.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TR026ControlError(invalid_code) from exc
    if not text.strip():
        raise TR026ControlError(missing_code)
    return text


def _reject_duplicate_json_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate private envelope field")
        result[key] = value
    return result


def _read_private_arm_envelope() -> dict:
    raw = _read_bounded_private_stdin(
        max_bytes=_ARM_ENVELOPE_MAX_BYTES,
        missing_code="arm_envelope_required_on_stdin",
        invalid_code="invalid_private_arm_envelope",
    )
    try:
        envelope = json.loads(raw, object_pairs_hook=_reject_duplicate_json_keys)
        if not isinstance(envelope, dict) or set(envelope) != _ARM_ENVELOPE_FIELDS:
            raise ValueError
        target = envelope.get("target")
        if not isinstance(target, dict) or set(target) != _ARM_TARGET_FIELDS:
            raise ValueError
        if (
            not isinstance(envelope.get("schema_version"), int)
            or isinstance(envelope.get("schema_version"), bool)
            or envelope["schema_version"] != _ARM_ENVELOPE_SCHEMA_VERSION
            or not isinstance(envelope.get("case_id"), str)
            or not isinstance(envelope.get("case_token"), str)
            or not isinstance(envelope.get("session_ref"), str)
        ):
            raise ValueError
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise TR026ControlError("invalid_private_arm_envelope") from exc
    return envelope


def _read_case_token_from_stdin() -> str:
    token = _read_bounded_private_stdin(
        max_bytes=256,
        missing_code="case_token_required_on_stdin",
        invalid_code="invalid_case_token",
    ).strip()
    if not token:
        raise TR026ControlError("case_token_required_on_stdin")
    try:
        return _strict_case_token(token)
    except ValueError as exc:
        raise TR026ControlError("invalid_case_token") from exc


def main(argv=None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.command == "arm":
            envelope = _read_private_arm_envelope()
            target = envelope["target"]
            receipt = arm_tr026_control(
                state_dir=args.state_dir,
                case_id=envelope["case_id"],
                case_token=envelope["case_token"],
                session_ref=envelope["session_ref"],
                owner_user_id=target["owner_user_id"],
                chat_id=target["chat_id"],
                thread_id=target["thread_id"],
                stale_source_sequence=target["stale_source_sequence"],
                source_sequence=target["source_sequence"],
                update_id=target["update_id"],
                ttl_seconds=envelope["ttl_seconds"],
            )
            print(json.dumps(asdict(receipt), sort_keys=True))
            return 0
        case_token = _read_case_token_from_stdin()
        if args.command == "cleanup":
            removed = cleanup_tr026_control(
                state_dir=args.state_dir,
                case_id=args.case_id,
                case_token=case_token,
                session_ref=args.session_ref,
            )
            print(
                json.dumps(
                    {
                        "artifact_ref": _token_digest(case_token)[:16],
                        "session_ref": args.session_ref,
                        "cleaned": removed,
                    },
                    sort_keys=True,
                )
            )
            return 0 if removed else 2
        evidence = read_redacted_audit(
            state_dir=args.state_dir,
            case_id=args.case_id,
            case_token=case_token,
            session_ref=args.session_ref,
        )
        print(
            json.dumps(
                {
                    "artifact_ref": _token_digest(case_token)[:16],
                    "session_ref": args.session_ref,
                    "evidence": evidence,
                },
                sort_keys=True,
            )
        )
        return 0
    except TR026ControlError as exc:
        error = exc.code
    except ValueError:
        error = "invalid_or_tampered_state"
    except (OSError, RuntimeError):
        error = "operation_failed"
    print(
        json.dumps({"case_id": TR026_CASE_ID, "error": error}, sort_keys=True),
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
