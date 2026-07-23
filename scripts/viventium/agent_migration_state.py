#!/usr/bin/env python3
"""Create the one-time, rollback-owned managed-agent migration handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import uuid
from pathlib import Path
from typing import Any


SHA40 = re.compile(r"^[a-f0-9]{40}$")
SHA64 = re.compile(r"^[a-f0-9]{64}$")
TRANSACTION_ID = re.compile(r"^upgrade-[A-Za-z0-9._-]{8,160}$")
LEGACY_PREDECESSOR_KEY = "VIVENTIUM_AGENT_PREDECESSOR_SOURCE_REF"
BUNDLE_PATHS = (
    "viventium/source_of_truth/local.viventium-agents.yaml",
    "tmp/viventium-agents.yaml",
    "scripts/viventium-agents.yaml",
    "scripts/viventium-agents-260127.yaml",
    "scripts/viventium-agents-260127-b.yaml",
    "scripts/viventium-agents-clawd.yaml",
)


class MigrationStateError(RuntimeError):
    pass


def stable_json(value: Any) -> str:
    if isinstance(value, list):
        return "[" + ",".join(stable_json(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(
            f"{json.dumps(key, ensure_ascii=False)}:{stable_json(value[key])}"
            for key in sorted(value)
        ) + "}"
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_stable(value: Any) -> str:
    return sha256_bytes(stable_json(value).encode("utf-8"))


def owned_regular_file(path: Path, label: str, *, exact_mode: int | None = None) -> Path:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise MigrationStateError(f"{label} is unavailable") from error
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or (exact_mode is not None and stat.S_IMODE(metadata.st_mode) != exact_mode)
    ):
        raise MigrationStateError(f"{label} is unsafe")
    return path


def ensure_private_directory(path: Path, boundary: Path) -> Path:
    root = Path(os.path.abspath(os.fspath(boundary.expanduser())))
    target = Path(os.path.abspath(os.fspath(path.expanduser())))
    try:
        target.relative_to(root)
    except ValueError as error:
        raise MigrationStateError("Migration state directory escapes App Support") from error
    current = root
    root_metadata = root.lstat()
    if not stat.S_ISDIR(root_metadata.st_mode) or root_metadata.st_uid != os.getuid():
        raise MigrationStateError("Viventium App Support root is unsafe")
    for part in target.relative_to(root).parts:
        current /= part
        if current.exists() or current.is_symlink():
            metadata = current.lstat()
            if (
                stat.S_ISLNK(metadata.st_mode)
                or not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_uid != os.getuid()
            ):
                raise MigrationStateError("Migration state directory is unsafe")
        else:
            current.mkdir(mode=0o700)
        if stat.S_IMODE(current.lstat().st_mode) != 0o700:
            current.chmod(0o700)
    return target


def read_component_lock(repo_root: Path) -> tuple[str, Path]:
    lock_path = owned_regular_file(repo_root / "components.lock.json", "Component lock")
    try:
        value = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MigrationStateError("Component lock is invalid") from error
    matches = [
        item
        for item in value.get("components", [])
        if isinstance(item, dict)
        and (item.get("name") == "LibreChat" or item.get("path") == "viventium_v0_4/LibreChat")
    ]
    if len(matches) != 1 or not SHA40.fullmatch(str(matches[0].get("ref") or "")):
        raise MigrationStateError("Component lock LibreChat identity is invalid")
    if matches[0].get("path") != "viventium_v0_4/LibreChat":
        raise MigrationStateError("Component lock LibreChat path is invalid")
    return str(matches[0]["ref"]), repo_root / "viventium_v0_4" / "LibreChat"


def git_text(repo: Path, *args: str) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def resolve_source_ref(repo_root: Path) -> tuple[str, str, Path]:
    root = Path(os.path.realpath(repo_root))
    if not root.is_dir() or root.is_symlink() or root.lstat().st_uid != os.getuid():
        raise MigrationStateError("Viventium repository root is unsafe")
    locked_ref, librechat = read_component_lock(root)
    if not librechat.is_dir() or librechat.is_symlink() or librechat.lstat().st_uid != os.getuid():
        raise MigrationStateError("LibreChat source root is unsafe")
    top_level = git_text(librechat, "rev-parse", "--show-toplevel")
    if top_level and Path(os.path.realpath(top_level)) == Path(os.path.realpath(librechat)):
        head = git_text(librechat, "rev-parse", "HEAD") or ""
        if not SHA40.fullmatch(head) or head != locked_ref:
            raise MigrationStateError("Nested LibreChat checkout does not match the component lock")
        return head, "nested_git", librechat
    required = [librechat / "scripts" / "viventium-seed-agents.js"]
    required.extend(librechat / candidate for candidate in BUNDLE_PATHS if (librechat / candidate).is_file())
    if len(required) < 2 or any(not item.is_file() or item.is_symlink() for item in required):
        raise MigrationStateError("Vendored LibreChat source is incomplete")
    return locked_ref, "vendored_lock", librechat


def detect_bundle(librechat: Path) -> Path:
    for relative in BUNDLE_PATHS:
        candidate = librechat / relative
        if candidate.is_file() and not candidate.is_symlink():
            return owned_regular_file(candidate, "Managed agent bundle")
    raise MigrationStateError("Managed agent bundle is unavailable")


def artifact_content(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("schema_version") == 1:
        return {"schema_version": 1, "migrations": value.get("migrations")}
    if value.get("schema_version") == 2:
        return {
            "schema_version": 2,
            "support_floor": value.get("support_floor"),
            "history_boundary": value.get("history_boundary"),
            "public_lock_revision_count": value.get("public_lock_revision_count"),
            "invalid_predecessors": value.get("invalid_predecessors"),
            "migrations": value.get("migrations"),
        }
    raise MigrationStateError("Managed migration registry schema is unsupported")


def read_registry(librechat: Path, predecessor_ref: str) -> tuple[Path, dict[str, Any]]:
    path = owned_regular_file(
        librechat / "viventium" / "source_of_truth" / "managed-agent-baseline-migration.json",
        "Managed migration registry",
    )
    if stat.S_IMODE(path.lstat().st_mode) & 0o022:
        raise MigrationStateError("Managed migration registry is writable by another user")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MigrationStateError("Managed migration registry is invalid") from error
    artifact_hash = str(value.get("artifact_sha256") or "")
    if not SHA64.fullmatch(artifact_hash) or artifact_hash != sha256_stable(artifact_content(value)):
        raise MigrationStateError("Managed migration registry hash is invalid")
    matches = [
        item
        for item in value.get("migrations", [])
        if predecessor_ref in item.get("predecessor_source_refs", [])
    ]
    if len(matches) != 1:
        raise MigrationStateError("Installed predecessor is outside the automatic migration floor")
    return path, value


def build_state(
    *,
    predecessor_ref: str,
    successor_ref: str,
    successor_bundle_sha256: str,
    registry_artifact_sha256: str,
    transaction_id: str,
) -> dict[str, Any]:
    content = {
        "schema_version": 1,
        "predecessor_source_ref": predecessor_ref,
        "successor_source_ref": successor_ref,
        "successor_bundle_sha256": successor_bundle_sha256,
        "registry_artifact_sha256": registry_artifact_sha256,
        "transaction_id": transaction_id,
    }
    if (
        not SHA40.fullmatch(predecessor_ref)
        or not SHA40.fullmatch(successor_ref)
        or not SHA64.fullmatch(successor_bundle_sha256)
        or not SHA64.fullmatch(registry_artifact_sha256)
        or not TRANSACTION_ID.fullmatch(transaction_id)
    ):
        raise MigrationStateError("Managed migration state identity is invalid")
    return {**content, "content_sha256": sha256_stable(content)}


def write_state_exclusive(path: Path, value: dict[str, Any], support: Path) -> None:
    ensure_private_directory(path.parent, support)
    if path.exists() or path.is_symlink():
        existing_path = owned_regular_file(
            path,
            "Pending managed agent migration",
            exact_mode=0o600,
        )
        try:
            existing = json.loads(existing_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise MigrationStateError("Pending managed agent migration is invalid") from error
        if existing == value:
            return
        raise MigrationStateError(
            "A different managed agent migration is already pending; start Viventium to finish it"
        )
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError as error:
            raise MigrationStateError("A managed agent migration appeared concurrently") from error
        path.chmod(0o600)
        directory_descriptor = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def read_legacy_predecessor(runtime_env: Path) -> tuple[str | None, list[str]]:
    path = owned_regular_file(runtime_env, "Generated runtime environment", exact_mode=0o600)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise MigrationStateError("Generated runtime environment is unreadable") from error
    values = [
        line.removeprefix(f"{LEGACY_PREDECESSOR_KEY}=")
        for line in lines
        if line.startswith(f"{LEGACY_PREDECESSOR_KEY}=")
    ]
    if not values:
        return None, lines
    if len(values) != 1 or not SHA40.fullmatch(values[0]):
        raise MigrationStateError("Legacy managed migration predecessor is ambiguous or invalid")
    return values[0], lines


def validated_upgrade_transaction_id(
    support: Path,
    repo_root: Path,
    librechat: Path,
    predecessor_ref: str,
    successor_ref: str,
) -> str:
    candidates = verified_upgrade_transactions(
        support,
        repo_root,
        librechat,
        successor_ref,
        predecessor_ref=predecessor_ref,
    )
    if not candidates:
        raise MigrationStateError("Legacy migration does not match a verified upgrade transaction")
    return max(candidates)[1]


def verified_upgrade_transactions(
    support: Path,
    repo_root: Path,
    librechat: Path,
    successor_ref: str,
    *,
    predecessor_ref: str | None = None,
) -> list[tuple[str, str, str]]:
    backup_root = support / "upgrade-backups"
    if not backup_root.exists() and not backup_root.is_symlink():
        return []
    backup_metadata = backup_root.lstat()
    if (
        stat.S_ISLNK(backup_metadata.st_mode)
        or not stat.S_ISDIR(backup_metadata.st_mode)
        or backup_metadata.st_uid != os.getuid()
    ):
        raise MigrationStateError("Protected upgrade evidence directory is unsafe")
    candidates: list[tuple[str, str, str]] = []
    for transaction in backup_root.glob("upgrade-*"):
        if (
            transaction.is_symlink()
            or not transaction.is_dir()
            or transaction.lstat().st_uid != os.getuid()
            or stat.S_IMODE(transaction.lstat().st_mode) != 0o700
        ):
            continue
        ledger_path = transaction / "ledger.json"
        try:
            owned_regular_file(ledger_path, "Upgrade transaction ledger", exact_mode=0o600)
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        except (MigrationStateError, OSError, json.JSONDecodeError):
            continue
        if (
            Path(os.path.realpath(str(ledger.get("transaction_path") or ""))) != transaction
            or Path(os.path.realpath(str(ledger.get("app_support_dir") or ""))) != support
            or Path(os.path.realpath(str(ledger.get("repo_root") or ""))) != repo_root
            or ledger.get("status") not in {"active", "committed"}
            or ledger.get("stage")
            not in {"candidate_activated", "restart_healthy", "committed"}
        ):
            continue
        runner = Path(os.path.realpath(str(ledger.get("transaction_runner") or "")))
        expected_runner_hash = str(ledger.get("transaction_runner_sha256") or "")
        try:
            runner.relative_to(transaction)
            owned_regular_file(runner, "Upgrade transaction runner", exact_mode=0o500)
        except (ValueError, MigrationStateError):
            continue
        if not SHA64.fullmatch(expected_runner_hash) or sha256_bytes(runner.read_bytes()) != expected_runner_hash:
            continue
        repositories = ledger.get("repositories")
        if not isinstance(repositories, list):
            continue
        nested_records = [
            record
            for record in repositories
            if isinstance(record, dict)
            if Path(os.path.realpath(str(record.get("path") or ""))) == librechat
        ]
        if len(nested_records) != 1:
            continue
        nested = nested_records[0]
        old_head = str(nested.get("old_head") or "")
        observed_heads = nested.get("observed_heads")
        if (
            not SHA40.fullmatch(old_head)
            or old_head == successor_ref
            or (predecessor_ref is not None and old_head != predecessor_ref)
            or not isinstance(observed_heads, list)
            or any(not SHA40.fullmatch(str(item)) for item in observed_heads)
            or successor_ref not in observed_heads
        ):
            continue
        transaction_id = transaction.name
        if not TRANSACTION_ID.fullmatch(transaction_id):
            continue
        candidates.append((str(ledger.get("created_at") or ""), transaction_id, old_head))
    return candidates


def discover_predecessor_from_upgrade_evidence(
    support: Path,
    repo_root: Path,
    librechat: Path,
    successor_ref: str,
) -> tuple[str, str] | None:
    candidates = sorted(
        verified_upgrade_transactions(support, repo_root, librechat, successor_ref),
        reverse=True,
    )
    if not candidates:
        return None
    _, transaction_id, predecessor_ref = candidates[0]
    try:
        read_registry(librechat, predecessor_ref)
    except MigrationStateError as error:
        raise MigrationStateError(
            "Verified installed predecessor is outside the automatic migration floor"
        ) from error
    return predecessor_ref, transaction_id


def build_import_receipt(
    *, predecessor_ref: str, successor_ref: str, transaction_id: str
) -> dict[str, Any]:
    content = {
        "schema_version": 1,
        "predecessor_source_ref": predecessor_ref,
        "successor_source_ref": successor_ref,
        "transaction_id": transaction_id,
    }
    if (
        not SHA40.fullmatch(predecessor_ref)
        or not SHA40.fullmatch(successor_ref)
        or not TRANSACTION_ID.fullmatch(transaction_id)
    ):
        raise MigrationStateError("Managed migration import receipt identity is invalid")
    return {**content, "content_sha256": sha256_stable(content)}


def read_import_receipt(path: Path, expected: dict[str, Any]) -> bool:
    if not path.exists() and not path.is_symlink():
        return False
    receipt_path = owned_regular_file(
        path,
        "Managed migration import receipt",
        exact_mode=0o600,
    )
    try:
        value = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MigrationStateError("Managed migration import receipt is invalid") from error
    if value != expected:
        raise MigrationStateError("Managed migration import receipt does not match upgrade evidence")
    return True


def write_import_receipt(path: Path, value: dict[str, Any], support: Path) -> None:
    ensure_private_directory(path.parent, support)
    if read_import_receipt(path, value):
        return
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError as error:
            raise MigrationStateError("Managed migration import receipt appeared concurrently") from error
        path.chmod(0o600)
        directory_descriptor = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def scrub_legacy_predecessor(runtime_env: Path, lines: list[str]) -> None:
    retained = [line for line in lines if not line.startswith(f"{LEGACY_PREDECESSOR_KEY}=")]
    temporary = runtime_env.with_name(f".{runtime_env.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write("\n".join(retained))
            if retained:
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, runtime_env)
        directory_descriptor = os.open(
            runtime_env.parent,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def command_prepare(args: argparse.Namespace) -> int:
    support = Path(os.path.abspath(os.fspath(args.app_support_dir.expanduser())))
    successor_ref, _, librechat = resolve_source_ref(args.repo_root)
    if successor_ref != args.successor_ref:
        raise MigrationStateError("Upgrade successor identity changed before migration handoff")
    bundle = detect_bundle(librechat)
    _, registry = read_registry(librechat, args.predecessor_ref)
    state = build_state(
        predecessor_ref=args.predecessor_ref,
        successor_ref=successor_ref,
        successor_bundle_sha256=sha256_bytes(bundle.read_bytes()),
        registry_artifact_sha256=str(registry["artifact_sha256"]),
        transaction_id=args.transaction_id,
    )
    state_path = support / "state" / "runtime" / "agent-managed-migration-pending.json"
    write_state_exclusive(state_path, state, support)
    print(json.dumps({"state_path": str(state_path), **state}, sort_keys=True))
    return 0


def command_source_ref(args: argparse.Namespace) -> int:
    source_ref, source_kind, _ = resolve_source_ref(args.repo_root)
    print(json.dumps({"source_ref": source_ref, "source_kind": source_kind}, sort_keys=True))
    return 0


def command_import_legacy(args: argparse.Namespace) -> int:
    support = Path(os.path.realpath(args.app_support_dir))
    repo_root = Path(os.path.realpath(args.repo_root))
    predecessor_ref, lines = read_legacy_predecessor(args.runtime_env)
    successor_ref, _, librechat = resolve_source_ref(repo_root)
    source = "runtime_marker"
    receipt_path: Path | None = None
    receipt: dict[str, Any] | None = None
    if predecessor_ref is None:
        discovered = discover_predecessor_from_upgrade_evidence(
            support,
            repo_root,
            librechat,
            successor_ref,
        )
        if discovered is None:
            print(json.dumps({"imported": False}, sort_keys=True))
            return 0
        predecessor_ref, transaction_id = discovered
        source = "verified_upgrade_ledger"
        receipt = build_import_receipt(
            predecessor_ref=predecessor_ref,
            successor_ref=successor_ref,
            transaction_id=transaction_id,
        )
        receipt_path = (
            support
            / "state"
            / "runtime"
            / "agent-managed-migration-imports"
            / f"{transaction_id}.json"
        )
        if read_import_receipt(receipt_path, receipt):
            print(json.dumps({"imported": False}, sort_keys=True))
            return 0
    else:
        transaction_id = validated_upgrade_transaction_id(
            support,
            repo_root,
            librechat,
            predecessor_ref,
            successor_ref,
        )
        receipt = build_import_receipt(
            predecessor_ref=predecessor_ref,
            successor_ref=successor_ref,
            transaction_id=transaction_id,
        )
        receipt_path = (
            support
            / "state"
            / "runtime"
            / "agent-managed-migration-imports"
            / f"{transaction_id}.json"
        )
        if read_import_receipt(receipt_path, receipt):
            scrub_legacy_predecessor(args.runtime_env, lines)
            print(json.dumps({"imported": False}, sort_keys=True))
            return 0
    bundle = detect_bundle(librechat)
    _, registry = read_registry(librechat, predecessor_ref)
    state = build_state(
        predecessor_ref=predecessor_ref,
        successor_ref=successor_ref,
        successor_bundle_sha256=sha256_bytes(bundle.read_bytes()),
        registry_artifact_sha256=str(registry["artifact_sha256"]),
        transaction_id=transaction_id,
    )
    state_path = support / "state" / "runtime" / "agent-managed-migration-pending.json"
    write_state_exclusive(state_path, state, support)
    if receipt_path is None or receipt is None:
        raise MigrationStateError("Managed migration import receipt was not prepared")
    write_import_receipt(receipt_path, receipt, support)
    if source == "runtime_marker":
        scrub_legacy_predecessor(args.runtime_env, lines)
    print(
        json.dumps(
            {"imported": True, "source": source, "state_path": str(state_path), **state},
            sort_keys=True,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    source = subparsers.add_parser("source-ref")
    source.add_argument("--repo-root", type=Path, required=True)
    source.set_defaults(handler=command_source_ref)
    legacy = subparsers.add_parser("import-legacy")
    legacy.add_argument("--repo-root", type=Path, required=True)
    legacy.add_argument("--app-support-dir", type=Path, required=True)
    legacy.add_argument("--runtime-env", type=Path, required=True)
    legacy.set_defaults(handler=command_import_legacy)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--repo-root", type=Path, required=True)
    prepare.add_argument("--app-support-dir", type=Path, required=True)
    prepare.add_argument("--predecessor-ref", required=True)
    prepare.add_argument("--successor-ref", required=True)
    prepare.add_argument("--transaction-id", required=True)
    prepare.set_defaults(handler=command_prepare)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.handler(args))
    except MigrationStateError as error:
        print(str(error), file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
