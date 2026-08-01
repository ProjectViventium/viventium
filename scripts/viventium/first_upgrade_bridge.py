#!/usr/bin/env python3
"""Successor-owned acceptance bridge for an already-running predecessor upgrader.

Shell functions do not change after ``git merge --ff-only``. A supported predecessor
therefore continues executing its old upgrade controller even though the dynamically
invoked compiler, launcher, continuity auditor, and helper installer now come from the
successor checkout. This module makes those successor entrypoints an explicit, verified
handoff instead of assuming the old shell acquired new safeguards.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT_DEFAULT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import upgrade_support
import upgrade_transaction


BRIDGE_SCHEMA_VERSION = 1
ACTIVE_POINTER = Path("state/upgrade-transaction-active.json")
BRIDGE_STATE = Path("state/continuity/first-upgrade-bridge.json")
QUIESCED_SESSION_STATE = Path("state/continuity/quiesced-upgrade-session.json")
POSTCOMMIT_API_FINALIZATION_STATE = Path(
    "state/continuity/postcommit-api-finalization.json"
)
POSTCOMMIT_API_REQUIRED_STAGES = (
    "database-connected",
    "database-seed-ready",
    "startup-checks-ready",
    "interface-permissions-ready",
    "mcp-runtime-ready",
    "oauth-reconnect-ready",
    "channel-persistence-ready",
    "permission-migration-inspection",
    "stale-cortex-recovery",
    "generation-runtime-ready",
)
SUCCESSOR_VALIDATION_DISABLED_WRITERS = (
    "agent-seeding,canonical-uploads,channel-workers,glasshive-callbacks,"
    "librechat-mcp-oauth,prompt-workbench,rag-recall,remote-mapping,scheduler,"
    "stale-cortex-recovery,telegram,telegram-codex,voice-workers"
)
LIBRECHAT_ENV_CHECKPOINT = Path("successor-bridge/librechat-runtime-env")
LIBRECHAT_ENV_CHECKPOINT_MANIFEST = Path(
    "successor-bridge/librechat-runtime-env-manifest.json"
)
HELPER_CONFIG_CHECKPOINT = Path("successor-bridge/helper-config")
HELPER_CONFIG_CHECKPOINT_MANIFEST = Path(
    "successor-bridge/helper-config-manifest.json"
)


class FirstUpgradeBridgeError(RuntimeError):
    """The successor could not prove a safe first-upgrade handoff."""


@dataclass(frozen=True)
class UpgradeContext:
    repo_root: Path
    app_support_dir: Path
    transaction: Path
    ledger: dict[str, Any]
    predecessor: str
    successor: str
    was_running: bool


@dataclass(frozen=True)
class MongoBridgeSpec:
    backend: str
    runtime_engine: str
    profile: str
    port: int
    database: str
    install_experience: str
    data_path: Path | None = None
    volume_name: str | None = None
    image: str | None = None
    image_id: str | None = None
    native_executable: Path | None = None
    native_executable_sha256: str | None = None
    native_version: str | None = None
    native_code_signature_verified: bool = False
    native_code_signature_team_identifier: str = ""


@dataclass(frozen=True)
class MongoBridgeSession:
    backend: str
    identity: dict[str, Any]
    environment: dict[str, str]


def lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def postcommit_finalization_id(transaction: Path, successor: str) -> str:
    if upgrade_support.SHA_RE.fullmatch(successor) is None:
        raise FirstUpgradeBridgeError("Post-commit finalization source identity is invalid")
    digest = hashlib.sha256()
    digest.update(b"viventium-postcommit-api-finalization-v1\0")
    digest.update(str(lexical(transaction)).encode("utf-8"))
    digest.update(b"\0")
    digest.update(successor.encode("ascii"))
    return digest.hexdigest()


def _verify_postcommit_api_finalization(
    *,
    app_support_dir: Path,
    run_id: str,
    source_id: str,
) -> dict[str, Any]:
    app_support_dir = lexical(app_support_dir)
    receipt_path = upgrade_transaction.contained(
        app_support_dir / POSTCOMMIT_API_FINALIZATION_STATE,
        app_support_dir,
        "post-commit API finalization receipt",
    )
    try:
        upgrade_transaction.validate_chain(receipt_path, owned_from=app_support_dir)
        metadata = receipt_path.lstat()
    except (FileNotFoundError, upgrade_transaction.UpgradeTransactionError) as error:
        raise FirstUpgradeBridgeError(
            "Post-commit API finalization proof is missing or unsafe"
        ) from error
    if (
        receipt_path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        raise FirstUpgradeBridgeError(
            "Post-commit API finalization proof is missing or unsafe"
        )
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FirstUpgradeBridgeError(
            "Post-commit API finalization proof is unreadable"
        ) from error
    completed = payload.get("completed")
    degraded = payload.get("degraded")
    if (
        payload.get("schemaVersion") != 1
        or payload.get("runId") != run_id
        or payload.get("sourceId") != source_id
        or payload.get("status") != "ready"
        or payload.get("stage") != "ready"
        or not isinstance(payload.get("attempt"), int)
        or isinstance(payload.get("attempt"), bool)
        or payload["attempt"] < 1
        or not isinstance(completed, list)
        or not all(isinstance(item, str) for item in completed)
        or not set(POSTCOMMIT_API_REQUIRED_STAGES).issubset(set(completed))
        or not isinstance(degraded, list)
        or {
            "stage": "derived-search-index",
            "code": "best-effort-derived-state",
        }
        not in degraded
    ):
        raise FirstUpgradeBridgeError(
            "Post-commit API finalization proof is incomplete or belongs to another run"
        )
    return {
        "status": "ready",
        "runId": run_id,
        "sourceId": source_id,
        "attempt": payload["attempt"],
        "completedStages": list(POSTCOMMIT_API_REQUIRED_STAGES),
        "degraded": [
            {
                "stage": "derived-search-index",
                "code": "best-effort-derived-state",
            }
        ],
    }


def git_text(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.stdout.strip()


def write_private_json(path: Path, payload: dict[str, Any], *, boundary: Path) -> None:
    target = upgrade_transaction.contained(path, boundary, "first-upgrade bridge state")
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    target.parent.chmod(0o700)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, target)
        target.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def _load_librechat_env_checkpoint(
    *,
    repo_root: Path,
    transaction: Path,
    expected_manifest_sha256: str = "",
) -> dict[str, Any]:
    manifest_path = upgrade_transaction.contained(
        transaction / LIBRECHAT_ENV_CHECKPOINT_MANIFEST,
        transaction,
        "first-upgrade LibreChat environment checkpoint manifest",
    )
    upgrade_transaction.validate_chain(manifest_path, owned_from=transaction)
    if (
        manifest_path.is_symlink()
        or not manifest_path.is_file()
        or manifest_path.lstat().st_uid != os.getuid()
    ):
        raise FirstUpgradeBridgeError(
            "First-upgrade LibreChat environment checkpoint is missing or unsafe"
        )
    if (
        expected_manifest_sha256
        and sha256_file(manifest_path) != expected_manifest_sha256
    ):
        raise FirstUpgradeBridgeError(
            "First-upgrade LibreChat environment checkpoint integrity failed"
        )
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FirstUpgradeBridgeError(
            "First-upgrade LibreChat environment checkpoint is unreadable"
        ) from error
    if (
        payload.get("schemaVersion") != 1
        or not isinstance(payload.get("surfaceManifest"), dict)
        or not isinstance(payload.get("backupManifest"), dict)
        or not isinstance(payload.get("semanticManifest"), dict)
    ):
        raise FirstUpgradeBridgeError(
            "First-upgrade LibreChat environment checkpoint is invalid"
        )
    backup = upgrade_transaction.contained(
        transaction / LIBRECHAT_ENV_CHECKPOINT,
        transaction,
        "first-upgrade LibreChat environment checkpoint",
    )
    expected_surface = payload["surfaceManifest"]
    expected_backup = payload["backupManifest"]
    try:
        actual_surface = upgrade_transaction.surface_manifest(backup)
        current_target = upgrade_transaction.librechat_runtime_env_path(repo_root)
    except upgrade_transaction.UpgradeTransactionError as error:
        raise FirstUpgradeBridgeError(
            "First-upgrade LibreChat environment checkpoint failed validation"
        ) from error
    if actual_surface != expected_backup:
        raise FirstUpgradeBridgeError(
            "First-upgrade LibreChat environment checkpoint content changed"
        )
    return {
        "manifestPath": manifest_path,
        "backup": backup,
        "target": current_target,
        "surfaceManifest": expected_surface,
        "semanticManifest": payload["semanticManifest"],
    }


def _required_librechat_env_checkpoint_sha256(payload: dict[str, Any]) -> str:
    digest = payload.get("librechatEnvCheckpointSha256")
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise FirstUpgradeBridgeError(
            "First-upgrade LibreChat environment checkpoint proof is missing"
        )
    return digest


def _required_helper_config_checkpoint_sha256(payload: dict[str, Any]) -> str:
    digest = payload.get("helperConfigCheckpointSha256")
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise FirstUpgradeBridgeError(
            "First-upgrade helper configuration checkpoint proof is missing"
        )
    return digest


def _checkpoint_librechat_env(context: UpgradeContext) -> dict[str, Any]:
    manifest_path = context.transaction / LIBRECHAT_ENV_CHECKPOINT_MANIFEST
    backup = context.transaction / LIBRECHAT_ENV_CHECKPOINT
    if (
        manifest_path.exists()
        or manifest_path.is_symlink()
        or backup.exists()
        or backup.is_symlink()
    ):
        return _load_librechat_env_checkpoint(
            repo_root=context.repo_root,
            transaction=context.transaction,
        )
    try:
        target = upgrade_transaction.librechat_runtime_env_path(context.repo_root)
        surface = upgrade_transaction.surface_manifest(target)
        upgrade_transaction.copy_surface(target, backup)
        if backup.exists():
            upgrade_transaction.make_immutable(backup)
        backup_surface = upgrade_transaction.surface_manifest(backup)
        semantic = upgrade_transaction.librechat_env_semantic_manifest(backup)
    except upgrade_transaction.UpgradeTransactionError as error:
        raise FirstUpgradeBridgeError(
            "First-upgrade LibreChat environment could not be checkpointed"
        ) from error
    write_private_json(
        manifest_path,
        {
            "schemaVersion": 1,
            "surfaceManifest": surface,
            "backupManifest": backup_surface,
            "semanticManifest": semantic,
        },
        boundary=context.transaction,
    )
    return _load_librechat_env_checkpoint(
        repo_root=context.repo_root,
        transaction=context.transaction,
    )


def _cleanup_successor_private_checkpoints(transaction: Path) -> bool:
    transaction = lexical(transaction)
    root = upgrade_transaction.contained(
        transaction / "successor-bridge",
        transaction,
        "first-upgrade successor checkpoint root",
    )
    if not root.exists() and not root.is_symlink():
        return True
    try:
        upgrade_transaction.validate_chain(root, owned_from=transaction)
        metadata = root.lstat()
        if (
            root.is_symlink()
            or not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.getuid()
        ):
            return False
        private_names = {
            LIBRECHAT_ENV_CHECKPOINT.name,
            LIBRECHAT_ENV_CHECKPOINT_MANIFEST.name,
            HELPER_CONFIG_CHECKPOINT.name,
            HELPER_CONFIG_CHECKPOINT_MANIFEST.name,
        }
        public_evidence_names = {
            "receipt.json",
            "stopped-baseline.json",
            "strict-comparison.json",
            "validated-live.json",
        }
        allowed = private_names | public_evidence_names
        if any(path.name not in allowed for path in root.iterdir()):
            return False
        root.chmod(0o700)
        for path in (
            transaction / LIBRECHAT_ENV_CHECKPOINT,
            transaction / LIBRECHAT_ENV_CHECKPOINT_MANIFEST,
            transaction / HELPER_CONFIG_CHECKPOINT,
            transaction / HELPER_CONFIG_CHECKPOINT_MANIFEST,
        ):
            if not path.exists() and not path.is_symlink():
                continue
            path_metadata = path.lstat()
            if (
                path.is_symlink()
                or not stat.S_ISREG(path_metadata.st_mode)
                or path_metadata.st_uid != os.getuid()
            ):
                return False
            path.unlink()
        if not any(root.iterdir()):
            root.rmdir()
            durable_directory = transaction
        else:
            durable_directory = root
        directory_descriptor = os.open(durable_directory, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
        return True
    except (OSError, upgrade_transaction.UpgradeTransactionError):
        return False


def _validated_committed_cleanup_transaction(
    *,
    transaction: Path,
    app_support_dir: Path,
    repo_root: Path,
) -> Path:
    app_support = lexical(app_support_dir)
    candidate = lexical(transaction)
    backup_root = lexical(app_support / upgrade_transaction.BACKUP_ROOT)
    try:
        upgrade_transaction.contained(
            candidate,
            backup_root,
            "first-upgrade cleanup transaction",
        )
    except upgrade_transaction.UpgradeTransactionError as error:
        raise FirstUpgradeBridgeError(
            "First-upgrade private cleanup transaction is outside App Support"
        ) from error
    if (
        candidate.parent != backup_root
        or not candidate.name.startswith("upgrade-")
    ):
        raise FirstUpgradeBridgeError(
            "First-upgrade private cleanup transaction is not canonical"
        )
    try:
        ledger = upgrade_transaction.load_ledger(candidate)
    except upgrade_transaction.UpgradeTransactionError as error:
        raise FirstUpgradeBridgeError(
            "Committed outer transaction proof failed before private cleanup"
        ) from error
    if (
        ledger.get("status") != "committed"
        or lexical(Path(str(ledger.get("app_support_dir") or ""))) != app_support
        or lexical(Path(str(ledger.get("repo_root") or ""))) != lexical(repo_root)
    ):
        raise FirstUpgradeBridgeError(
            "Committed outer transaction scope changed before private cleanup"
        )
    return candidate


def _load_helper_config_checkpoint(
    *,
    app_support_dir: Path,
    transaction: Path,
    expected_manifest_sha256: str = "",
) -> dict[str, Any]:
    manifest_path = upgrade_transaction.contained(
        transaction / HELPER_CONFIG_CHECKPOINT_MANIFEST,
        transaction,
        "first-upgrade helper configuration checkpoint manifest",
    )
    upgrade_transaction.validate_chain(manifest_path, owned_from=transaction)
    if (
        manifest_path.is_symlink()
        or not manifest_path.is_file()
        or manifest_path.lstat().st_uid != os.getuid()
    ):
        raise FirstUpgradeBridgeError(
            "First-upgrade helper configuration checkpoint is missing or unsafe"
        )
    if (
        expected_manifest_sha256
        and sha256_file(manifest_path) != expected_manifest_sha256
    ):
        raise FirstUpgradeBridgeError(
            "First-upgrade helper configuration checkpoint integrity failed"
        )
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FirstUpgradeBridgeError(
            "First-upgrade helper configuration checkpoint is unreadable"
        ) from error
    if (
        payload.get("schemaVersion") != 1
        or not isinstance(payload.get("surfaceManifest"), dict)
        or not isinstance(payload.get("backupManifest"), dict)
        or not isinstance(payload.get("semanticManifest"), dict)
    ):
        raise FirstUpgradeBridgeError(
            "First-upgrade helper configuration checkpoint is invalid"
        )
    backup = upgrade_transaction.contained(
        transaction / HELPER_CONFIG_CHECKPOINT,
        transaction,
        "first-upgrade helper configuration checkpoint",
    )
    try:
        actual_backup = upgrade_transaction.surface_manifest(backup)
        current_target = upgrade_transaction.helper_config_path(app_support_dir)
    except upgrade_transaction.UpgradeTransactionError as error:
        raise FirstUpgradeBridgeError(
            "First-upgrade helper configuration checkpoint failed validation"
        ) from error
    if actual_backup != payload["backupManifest"]:
        raise FirstUpgradeBridgeError(
            "First-upgrade helper configuration checkpoint content changed"
        )
    return {
        "manifestPath": manifest_path,
        "backup": backup,
        "target": current_target,
        "surfaceManifest": payload["surfaceManifest"],
        "semanticManifest": payload["semanticManifest"],
    }


def _checkpoint_helper_config(context: UpgradeContext) -> dict[str, Any]:
    manifest_path = context.transaction / HELPER_CONFIG_CHECKPOINT_MANIFEST
    backup = context.transaction / HELPER_CONFIG_CHECKPOINT
    if (
        manifest_path.exists()
        or manifest_path.is_symlink()
        or backup.exists()
        or backup.is_symlink()
    ):
        return _load_helper_config_checkpoint(
            app_support_dir=context.app_support_dir,
            transaction=context.transaction,
        )
    try:
        target = upgrade_transaction.helper_config_path(context.app_support_dir)
        surface = upgrade_transaction.surface_manifest(target)
        upgrade_transaction.copy_surface(target, backup)
        if backup.exists():
            upgrade_transaction.make_immutable(backup)
        backup_surface = upgrade_transaction.surface_manifest(backup)
        semantic = upgrade_transaction.helper_config_semantic_manifest(backup)
    except upgrade_transaction.UpgradeTransactionError as error:
        raise FirstUpgradeBridgeError(
            "First-upgrade helper configuration could not be checkpointed"
        ) from error
    write_private_json(
        manifest_path,
        {
            "schemaVersion": 1,
            "surfaceManifest": surface,
            "backupManifest": backup_surface,
            "semanticManifest": semantic,
        },
        boundary=context.transaction,
    )
    return _load_helper_config_checkpoint(
        app_support_dir=context.app_support_dir,
        transaction=context.transaction,
    )


def _verify_helper_config_after_full_start(
    *,
    app_support_dir: Path,
    transaction: Path,
    expected_manifest_sha256: str,
) -> dict[str, Any]:
    checkpoint = _load_helper_config_checkpoint(
        app_support_dir=app_support_dir,
        transaction=transaction,
        expected_manifest_sha256=expected_manifest_sha256,
    )
    try:
        after = upgrade_transaction.helper_config_semantic_manifest(
            checkpoint["target"]
        )
        return upgrade_transaction.compare_helper_config_semantic_manifests(
            checkpoint["semanticManifest"],
            after,
        )
    except upgrade_transaction.UpgradeTransactionError as error:
        raise FirstUpgradeBridgeError(
            "First-upgrade full runtime changed protected helper configuration"
        ) from error


def _restore_helper_config_checkpoint(
    *,
    app_support_dir: Path,
    transaction: Path,
    expected_manifest_sha256: str,
) -> None:
    checkpoint = _load_helper_config_checkpoint(
        app_support_dir=app_support_dir,
        transaction=transaction,
        expected_manifest_sha256=expected_manifest_sha256,
    )
    try:
        upgrade_transaction.replace_surface_from(
            checkpoint["backup"],
            checkpoint["target"],
            checkpoint["surfaceManifest"],
            transaction,
            "first-upgrade-helper-configuration",
        )
    except upgrade_transaction.UpgradeTransactionError as error:
        raise FirstUpgradeBridgeError(
            "First-upgrade helper configuration recovery failed"
        ) from error


def _verify_librechat_env_after_full_start(
    *,
    repo_root: Path,
    transaction: Path,
    expected_manifest_sha256: str,
) -> dict[str, Any]:
    checkpoint = _load_librechat_env_checkpoint(
        repo_root=repo_root,
        transaction=transaction,
        expected_manifest_sha256=expected_manifest_sha256,
    )
    try:
        after = upgrade_transaction.librechat_env_semantic_manifest(
            checkpoint["target"]
        )
        return upgrade_transaction.compare_librechat_env_semantic_manifests(
            checkpoint["semanticManifest"],
            after,
        )
    except upgrade_transaction.UpgradeTransactionError as error:
        raise FirstUpgradeBridgeError(
            "First-upgrade full runtime changed protected LibreChat environment state"
        ) from error


def _restore_librechat_env_checkpoint(
    *,
    repo_root: Path,
    transaction: Path,
    expected_manifest_sha256: str,
) -> None:
    checkpoint = _load_librechat_env_checkpoint(
        repo_root=repo_root,
        transaction=transaction,
        expected_manifest_sha256=expected_manifest_sha256,
    )
    try:
        upgrade_transaction.replace_surface_from(
            checkpoint["backup"],
            checkpoint["target"],
            checkpoint["surfaceManifest"],
            transaction,
            "first-upgrade-librechat-runtime-env",
        )
    except upgrade_transaction.UpgradeTransactionError as error:
        raise FirstUpgradeBridgeError(
            "First-upgrade LibreChat environment recovery failed"
        ) from error


def _read_pointer(app_support_dir: Path) -> tuple[Path, dict[str, Any]] | None:
    pointer = app_support_dir / ACTIVE_POINTER
    if not pointer.exists() and not pointer.is_symlink():
        return None
    upgrade_transaction.validate_chain(pointer, owned_from=app_support_dir)
    metadata = pointer.lstat()
    if (
        pointer.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
    ):
        raise FirstUpgradeBridgeError("Active upgrade transaction pointer is unsafe")
    try:
        payload = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FirstUpgradeBridgeError("Active upgrade transaction pointer is unreadable") from error
    transaction = lexical(Path(str(payload.get("transaction_path") or "")))
    if payload.get("schema_version") != upgrade_transaction.SCHEMA_VERSION:
        raise FirstUpgradeBridgeError("Active upgrade transaction pointer schema is unsupported")
    return transaction, payload


def load_active_context(
    *,
    repo_root: Path,
    app_support_dir: Path,
    required_stage: str | None = None,
    allow_same_source: bool = False,
) -> UpgradeContext | None:
    repo_root = lexical(repo_root)
    app_support_dir = lexical(app_support_dir)
    pointer = _read_pointer(app_support_dir)
    if pointer is None:
        return None
    transaction, _ = pointer
    try:
        ledger = upgrade_transaction.load_ledger(transaction)
    except upgrade_transaction.UpgradeTransactionError as error:
        raise FirstUpgradeBridgeError("Immutable upgrade transaction proof failed") from error
    if (
        lexical(Path(str(ledger.get("repo_root") or ""))) != repo_root
        or lexical(Path(str(ledger.get("app_support_dir") or ""))) != app_support_dir
        or ledger.get("status") != "active"
    ):
        raise FirstUpgradeBridgeError("Active upgrade transaction scope is inconsistent")
    if required_stage is not None and ledger.get("stage") != required_stage:
        return None

    parent_records = [
        record
        for record in ledger.get("repositories", [])
        if record.get("name") == "parent"
    ]
    if len(parent_records) != 1:
        raise FirstUpgradeBridgeError("Upgrade transaction parent source proof is ambiguous")
    predecessor = str(parent_records[0].get("old_head") or "")
    successor = git_text(repo_root, "rev-parse", "HEAD")
    if (
        not upgrade_support.SHA_RE.fullmatch(predecessor)
        or not upgrade_support.SHA_RE.fullmatch(successor)
    ):
        raise FirstUpgradeBridgeError("Upgrade source identities are invalid")
    if predecessor == successor and not allow_same_source:
        return None
    if predecessor != successor:
        ancestor = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "merge-base",
                "--is-ancestor",
                predecessor,
                successor,
            ],
            check=False,
            capture_output=True,
            timeout=30,
        )
        if ancestor.returncode != 0:
            raise FirstUpgradeBridgeError(
                "Upgrade successor is not a descendant of its predecessor"
            )
        policy = upgrade_support.load_policy(
            repo_root / "release" / "upgrade-support.json"
        )
        assessment = upgrade_support.assess_predecessor(repo_root, policy, predecessor)
        if not assessment["supported"]:
            raise FirstUpgradeBridgeError(
                "Installed predecessor is outside the reviewed first-upgrade support range"
            )
    return UpgradeContext(
        repo_root=repo_root,
        app_support_dir=app_support_dir,
        transaction=transaction,
        ledger=ledger,
        predecessor=predecessor,
        successor=successor,
        was_running=bool(ledger.get("was_running")),
    )


def _surface_backup(context: UpgradeContext, label: str) -> Path:
    matches = [
        surface
        for surface in context.ledger.get("surfaces", [])
        if surface.get("label") == label
    ]
    if len(matches) != 1:
        raise FirstUpgradeBridgeError(f"Stopped {label} checkpoint is missing or ambiguous")
    return upgrade_transaction.contained(
        Path(str(matches[0].get("backup") or "")),
        context.transaction,
        f"stopped {label} checkpoint",
    )


def _bridge_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["VIVENTIUM_FIRST_UPGRADE_BRIDGE_INTERNAL"] = "1"
    environment["VIVENTIUM_QUIESCED_FINALIZATION_INTERNAL"] = "1"
    environment["VIVENTIUM_CLI_LOCK_INHERITED_ONCE"] = "1"
    environment["VIVENTIUM_TELEGRAM_PREDECESSOR_RUNTIME"] = "0"
    return environment


def _run_checked(command: list[str], *, environment: dict[str, str], timeout: int) -> None:
    completed = subprocess.run(
        command,
        check=False,
        env=environment,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise FirstUpgradeBridgeError(
            f"Successor-owned upgrade validation failed at {Path(command[0]).name}"
        )


def _run_capture(
    command: list[str],
    *,
    environment: dict[str, str],
    timeout: int,
) -> str:
    try:
        completed = subprocess.run(
            command,
            check=False,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise FirstUpgradeBridgeError(
            f"Successor-owned upgrade validation failed at {Path(command[0]).name}"
        ) from error
    if completed.returncode != 0:
        raise FirstUpgradeBridgeError(
            f"Successor-owned upgrade validation failed at {Path(command[0]).name}"
        )
    return completed.stdout


def _runtime_surface_record(
    context: UpgradeContext,
    checkpoint_runtime: Path,
) -> dict[str, Any]:
    matches = [
        surface
        for surface in context.ledger.get("surfaces", [])
        if surface.get("label") == "runtime"
    ]
    if len(matches) != 1:
        raise FirstUpgradeBridgeError("Stopped runtime checkpoint is missing or ambiguous")
    recorded = upgrade_transaction.contained(
        Path(str(matches[0].get("backup") or "")),
        context.transaction,
        "stopped runtime checkpoint",
    )
    if recorded != lexical(checkpoint_runtime):
        raise FirstUpgradeBridgeError("Stopped runtime checkpoint identity changed")
    manifest = matches[0].get("manifest")
    if not isinstance(manifest, dict) or manifest.get("kind") != "directory":
        raise FirstUpgradeBridgeError("Stopped runtime checkpoint manifest is invalid")
    return matches[0]


def _checkpoint_runtime_values(
    context: UpgradeContext,
    checkpoint_runtime: Path,
) -> dict[str, str]:
    checkpoint_runtime = upgrade_transaction.contained(
        checkpoint_runtime,
        context.transaction,
        "stopped runtime checkpoint",
    )
    record = _runtime_surface_record(context, checkpoint_runtime)
    upgrade_transaction.validate_chain(
        checkpoint_runtime,
        owned_from=context.transaction,
    )
    metadata = checkpoint_runtime.lstat()
    if (
        checkpoint_runtime.is_symlink()
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) & 0o222
    ):
        raise FirstUpgradeBridgeError("Stopped runtime checkpoint is not immutable")

    manifest_entries = {
        str(item.get("path") or ""): item
        for item in record["manifest"].get("files", [])
        if isinstance(item, dict)
    }
    allowed = {
        "VIVENTIUM_RUNTIME_PROFILE",
        "VIVENTIUM_INSTALL_MODE",
        "VIVENTIUM_LOCAL_MONGO_PORT",
        "VIVENTIUM_LOCAL_MONGO_DB",
        "VIVENTIUM_INSTALL_EXPERIENCE",
        "MONGO_IMAGE",
    }
    values: dict[str, str] = {}
    for name in ("runtime.env", "runtime.local.env"):
        path = checkpoint_runtime / name
        if not path.exists() and not path.is_symlink():
            continue
        expected = manifest_entries.get(name)
        upgrade_transaction.validate_chain(path, owned_from=context.transaction)
        path_metadata = path.lstat()
        if (
            expected is None
            or path.is_symlink()
            or not stat.S_ISREG(path_metadata.st_mode)
            or path_metadata.st_uid != os.getuid()
            or stat.S_IMODE(path_metadata.st_mode) & 0o222
            or path_metadata.st_size != expected.get("size")
            or sha256_file(path) != expected.get("sha256")
        ):
            raise FirstUpgradeBridgeError(
                "Stopped runtime checkpoint environment failed verification"
            )
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as error:
            raise FirstUpgradeBridgeError(
                "Stopped runtime checkpoint environment is unreadable"
            ) from error
        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :]
            if "=" not in line:
                continue
            key, raw_value = line.split("=", 1)
            key = key.strip()
            if key not in allowed:
                continue
            try:
                parsed = shlex.split(raw_value, comments=True, posix=True)
            except ValueError as error:
                raise FirstUpgradeBridgeError(
                    "Stopped runtime checkpoint environment is malformed"
                ) from error
            if len(parsed) > 1:
                raise FirstUpgradeBridgeError(
                    "Stopped runtime checkpoint environment is ambiguous"
                )
            values[key] = parsed[0] if parsed else ""
    return values


def _checkpoint_mongo_spec(
    context: UpgradeContext,
    checkpoint_runtime: Path,
) -> MongoBridgeSpec:
    inventory = context.ledger.get("storage_inventory", {}).get("mongodb")
    if not isinstance(inventory, dict):
        raise FirstUpgradeBridgeError("Stopped MongoDB storage inventory is missing")
    if (
        inventory.get("checkpoint_status") != "complete"
        or inventory.get("existed_before") is not True
    ):
        raise FirstUpgradeBridgeError("Stopped MongoDB checkpoint is incomplete")

    values = _checkpoint_runtime_values(context, checkpoint_runtime)
    profile = str(inventory.get("profile") or "").strip().lower()
    recorded_profile = (
        values.get("VIVENTIUM_RUNTIME_PROFILE", "isolated").strip().lower()
        or "isolated"
    )
    if (
        not re.fullmatch(r"[a-z0-9_.-]{1,64}", profile)
        or recorded_profile != profile
    ):
        raise FirstUpgradeBridgeError(
            "Stopped MongoDB profile does not match its checkpoint environment"
        )
    raw_port = values.get("VIVENTIUM_LOCAL_MONGO_PORT", "27117").strip()
    try:
        port = int(raw_port)
    except ValueError as error:
        raise FirstUpgradeBridgeError("Stopped MongoDB port is invalid") from error
    if not 1 <= port <= 65535 or str(port) != raw_port:
        raise FirstUpgradeBridgeError("Stopped MongoDB port is invalid")
    database = values.get("VIVENTIUM_LOCAL_MONGO_DB", "LibreChatViventium").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", database):
        raise FirstUpgradeBridgeError("Stopped MongoDB database name is unsafe")
    experience = values.get("VIVENTIUM_INSTALL_EXPERIENCE", "legacy").strip().lower()
    if not re.fullmatch(r"[a-z0-9_.-]{1,64}", experience):
        raise FirstUpgradeBridgeError("Stopped install experience is unsafe")

    backend = str(inventory.get("backend") or "")
    if backend == "app_support_bind":
        try:
            data_path = upgrade_transaction.contained(
                Path(str(inventory.get("path") or "")),
                context.app_support_dir,
                "recorded MongoDB data path",
            )
            upgrade_transaction.validate_chain(
                data_path,
                owned_from=context.app_support_dir,
            )
        except upgrade_transaction.UpgradeTransactionError as error:
            raise FirstUpgradeBridgeError(
                "Recorded MongoDB data path is unsafe"
            ) from error
        if (
            data_path.is_symlink()
            or not data_path.is_dir()
            or data_path.lstat().st_uid != os.getuid()
        ):
            raise FirstUpgradeBridgeError("Recorded MongoDB data path is unavailable")
        observed_from = str(inventory.get("observed_from") or "")
        runtime_engine = str(inventory.get("runtime_engine") or "")
        if not runtime_engine:
            if observed_from == "running_native_pid":
                runtime_engine = "native"
            else:
                # The accepted d59 predecessor records isolated/explicit Docker
                # bind storage only as app_support_bind. Its launcher may have
                # selected either a container or host fallback at runtime, and
                # that old ledger has no immutable engine/image proof. Never
                # guess and open the same WiredTiger files with another engine.
                raise FirstUpgradeBridgeError(
                    "Stopped MongoDB runtime engine proof is missing"
                )
        if runtime_engine not in {"native", "docker"}:
            raise FirstUpgradeBridgeError("Stopped MongoDB runtime engine is unsupported")
        native_identity: dict[str, Any] = {}
        if runtime_engine == "native":
            try:
                executable = Path(str(inventory.get("executable") or ""))
                if (
                    not executable.is_absolute()
                    or executable.is_symlink()
                    or not executable.is_file()
                ):
                    raise FirstUpgradeBridgeError(
                        "Stopped native MongoDB executable proof is missing"
                    )
                executable_sha256 = str(
                    inventory.get("executable_sha256") or ""
                )
                if (
                    not re.fullmatch(r"[0-9a-f]{64}", executable_sha256)
                    or upgrade_transaction.sha256_file(executable)
                    != executable_sha256
                ):
                    raise FirstUpgradeBridgeError(
                        "Stopped native MongoDB executable hash changed"
                    )
                recorded_arguments = inventory.get("arguments")
                if not isinstance(recorded_arguments, list):
                    raise FirstUpgradeBridgeError(
                        "Stopped native MongoDB process arguments are missing"
                    )
                recorded_dbpath = upgrade_transaction.contained(
                    upgrade_transaction.native_mongo_dbpath(
                        {"arguments": recorded_arguments}
                    ),
                    context.app_support_dir,
                    "recorded native MongoDB dbpath",
                )
                if recorded_dbpath != data_path:
                    raise FirstUpgradeBridgeError(
                        "Stopped native MongoDB dbpath proof changed"
                    )
                native_version = str(inventory.get("version") or "")
                if not native_version or not str(
                    inventory.get("process_started_at") or ""
                ):
                    raise FirstUpgradeBridgeError(
                        "Stopped native MongoDB process/version proof is missing"
                    )
                version_check = subprocess.run(
                    [str(executable), "--version"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                actual_version = next(
                    (
                        line.strip()
                        for line in version_check.stdout.splitlines()
                        if line.strip()
                    ),
                    "",
                )
                if version_check.returncode != 0 or actual_version != native_version:
                    raise FirstUpgradeBridgeError(
                        "Stopped native MongoDB executable version changed"
                    )
                native_identity = {
                    "native_executable": executable,
                    "native_executable_sha256": executable_sha256,
                    "native_version": native_version,
                    "native_code_signature_verified": (
                        inventory.get("code_signature_verified") is True
                    ),
                    "native_code_signature_team_identifier": str(
                        inventory.get("code_signature_team_identifier") or ""
                    ),
                }
            except (
                OSError,
                subprocess.TimeoutExpired,
                upgrade_transaction.UpgradeTransactionError,
            ) as error:
                raise FirstUpgradeBridgeError(
                    "Stopped native MongoDB executable proof is invalid"
                ) from error
        image: str | None = None
        image_id: str | None = None
        if runtime_engine == "docker":
            try:
                image = upgrade_transaction.validate_docker_image(
                    str(inventory.get("image") or "")
                )
                raw_image_id = str(inventory.get("image_id") or "")
                image_id = (
                    upgrade_transaction.validate_docker_image_id(raw_image_id)
                    if raw_image_id
                    else None
                )
            except upgrade_transaction.UpgradeTransactionError as error:
                raise FirstUpgradeBridgeError(
                    "Stopped Docker-bind MongoDB engine/image proof is missing"
                ) from error
        return MongoBridgeSpec(
            backend=backend,
            runtime_engine=runtime_engine,
            profile=profile,
            port=port,
            database=database,
            install_experience=experience,
            data_path=data_path,
            image=image,
            image_id=image_id,
            **native_identity,
        )
    if backend == "docker_named_volume":
        try:
            volume = upgrade_transaction.validate_docker_name(
                str(inventory.get("volume_name") or ""),
                "MongoDB volume name",
            )
            image = upgrade_transaction.validate_docker_image(
                str(inventory.get("image") or "")
            )
            raw_image_id = str(inventory.get("image_id") or "")
            image_id = (
                upgrade_transaction.validate_docker_image_id(raw_image_id)
                if raw_image_id
                else None
            )
        except upgrade_transaction.UpgradeTransactionError as error:
            raise FirstUpgradeBridgeError(
                "Recorded Docker MongoDB identity is unsafe"
            ) from error
        return MongoBridgeSpec(
            backend=backend,
            runtime_engine="docker",
            profile=profile,
            port=port,
            database=database,
            install_experience=experience,
            volume_name=volume,
            image=image,
            image_id=image_id,
        )
    raise FirstUpgradeBridgeError("Stopped MongoDB backend is unsupported")


def _native_bridge_environment(
    context: UpgradeContext,
    spec: MongoBridgeSpec,
) -> dict[str, str]:
    if spec.data_path is None:
        raise FirstUpgradeBridgeError("Recorded native MongoDB path is missing")
    environment = _bridge_environment()
    environment.update(
        {
            "VIVENTIUM_APP_SUPPORT_DIR": str(context.app_support_dir),
            "VIVENTIUM_BASE_STATE_DIR": str(context.app_support_dir / "state"),
            "VIVENTIUM_RUNTIME_PROFILE": spec.profile,
            "VIVENTIUM_LOCAL_MONGO_DATA_PATH": str(spec.data_path),
            "VIVENTIUM_LOCAL_MONGO_PORT": str(spec.port),
            "VIVENTIUM_LOCAL_MONGO_DB": spec.database,
            "MONGO_HOST": "127.0.0.1",
            "VIVENTIUM_INSTALL_EXPERIENCE": spec.install_experience,
            "VIVENTIUM_NATIVE_STACK_SKIP_LIVEKIT": "1",
            "VIVENTIUM_NATIVE_STACK_SKIP_MEILI": "1",
            "VIVENTIUM_VOICE_ENABLED": "false",
        }
    )
    if spec.native_executable is None:
        raise FirstUpgradeBridgeError(
            "Recorded native MongoDB executable identity is incomplete"
        )
    environment["VIVENTIUM_BRIDGE_MONGOD_BINARY"] = str(spec.native_executable)
    return environment


def _docker_bridge_identity(
    context: UpgradeContext,
) -> tuple[str, dict[str, str]]:
    token = hashlib.sha256(str(context.transaction).encode("utf-8")).hexdigest()
    return (
        f"viventium-first-upgrade-mongo-{token[:20]}",
        {
            "com.viventium.first-upgrade.role": "checkpoint-mongodb",
            "com.viventium.first-upgrade.transaction": token,
        },
    )


def _docker_run_args(
    spec: MongoBridgeSpec,
    *,
    name: str,
    labels: dict[str, str],
) -> list[str]:
    if spec.image is None:
        raise FirstUpgradeBridgeError("Recorded Docker MongoDB identity is incomplete")
    immutable_image = spec.image_id or spec.image
    if spec.image_id is None and not (
        re.search(r"@sha256:[0-9a-f]{64}$", spec.image)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", spec.image)
    ):
        raise FirstUpgradeBridgeError(
            "Recorded Docker MongoDB immutable image identity is incomplete"
        )
    if spec.backend == "docker_named_volume" and spec.volume_name is not None:
        mount = f"type=volume,source={spec.volume_name},target=/data/db"
    elif (
        spec.backend == "app_support_bind"
        and spec.runtime_engine == "docker"
        and spec.data_path is not None
    ):
        mount = f"type=bind,source={spec.data_path},target=/data/db"
    else:
        raise FirstUpgradeBridgeError("Recorded Docker MongoDB identity is incomplete")
    arguments = [
        "run",
        "--detach",
        "--pull",
        "never",
        "--name",
        name,
        "--restart",
        "no",
        "--publish",
        f"127.0.0.1:{spec.port}:27017",
        "--mount",
        mount,
        "--tmpfs",
        "/data/configdb",
    ]
    for key, value in sorted(labels.items()):
        arguments.extend(["--label", f"{key}={value}"])
    arguments.append(immutable_image)
    return arguments


def _docker_call(
    arguments: list[str],
    *,
    check: bool = True,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    docker = shutil.which("docker")
    if not docker:
        raise FirstUpgradeBridgeError(
            "Docker is required for the recorded MongoDB checkpoint"
        )
    try:
        completed = subprocess.run(
            [docker, *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise FirstUpgradeBridgeError(
            "Docker MongoDB bridge command did not complete safely"
        ) from error
    if check and completed.returncode != 0:
        raise FirstUpgradeBridgeError("Docker MongoDB bridge command failed")
    return completed


def _docker_inspect(
    identifier: str,
    *,
    allow_missing: bool = False,
) -> dict[str, Any] | None:
    completed = _docker_call(
        ["container", "inspect", identifier],
        check=False,
    )
    if completed.returncode != 0:
        if allow_missing:
            return None
        raise FirstUpgradeBridgeError("Docker MongoDB bridge container is missing")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise FirstUpgradeBridgeError(
            "Docker MongoDB bridge identity is unreadable"
        ) from error
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        raise FirstUpgradeBridgeError("Docker MongoDB bridge identity is ambiguous")
    return payload[0]


def _verify_docker_container(
    container: dict[str, Any],
    spec: MongoBridgeSpec,
    *,
    name: str,
    labels: dict[str, str],
    expected_id: str | None = None,
    require_running: bool = False,
) -> str:
    container_id = str(container.get("Id") or "")
    config = container.get("Config")
    host_config = container.get("HostConfig")
    mounts = container.get("Mounts")
    state = container.get("State")
    if (
        not re.fullmatch(r"[0-9a-f]{12,64}", container_id)
        or (expected_id is not None and container_id != expected_id)
        or str(container.get("Name") or "").lstrip("/") != name
        or not isinstance(config, dict)
        or config.get("Image") != (spec.image_id or spec.image)
        or (
            spec.image_id is not None
            and container.get("Image") != spec.image_id
        )
        or not isinstance(config.get("Labels"), dict)
        or any(config["Labels"].get(key) != value for key, value in labels.items())
        or not isinstance(host_config, dict)
        or host_config.get("RestartPolicy", {}).get("Name") not in {"", "no"}
        or not isinstance(mounts, list)
    ):
        raise FirstUpgradeBridgeError("Docker MongoDB bridge identity mismatch")
    data_mounts = [
        mount
        for mount in mounts
        if isinstance(mount, dict) and mount.get("Destination") == "/data/db"
    ]
    expected_ports = {
        "27017/tcp": [
            {"HostIp": "127.0.0.1", "HostPort": str(spec.port)}
        ]
    }
    expected_mount_type = (
        "volume" if spec.backend == "docker_named_volume" else "bind"
    )
    expected_mount_identity = (
        spec.volume_name
        if expected_mount_type == "volume"
        else str(spec.data_path)
    )
    actual_mount_identity = (
        data_mounts[0].get("Name")
        if data_mounts and expected_mount_type == "volume"
        else data_mounts[0].get("Source") if data_mounts else None
    )
    if (
        len(data_mounts) != 1
        or data_mounts[0].get("Type") != expected_mount_type
        or actual_mount_identity != expected_mount_identity
        or host_config.get("PortBindings") != expected_ports
        or (
            require_running
            and (not isinstance(state, dict) or state.get("Running") is not True)
        )
    ):
        raise FirstUpgradeBridgeError("Docker MongoDB bridge identity mismatch")
    return container_id


def _remove_interrupted_docker_bridge(
    spec: MongoBridgeSpec,
    *,
    name: str,
    labels: dict[str, str],
) -> None:
    existing = _docker_inspect(name, allow_missing=True)
    if existing is None:
        return
    container_id = _verify_docker_container(
        existing,
        spec,
        name=name,
        labels=labels,
    )
    state = existing.get("State")
    if isinstance(state, dict) and state.get("Running") is True:
        _docker_call(["container", "stop", "--time", "30", container_id])
    _docker_call(["container", "rm", container_id])
    if _docker_inspect(container_id, allow_missing=True) is not None:
        raise FirstUpgradeBridgeError(
            "Docker MongoDB bridge cleanup did not remove its exact container"
        )


def _start_native_checkpoint_mongo(
    context: UpgradeContext,
    spec: MongoBridgeSpec,
) -> MongoBridgeSession:
    environment = _native_bridge_environment(context, spec)
    output = _run_capture(
        [
            str(context.repo_root / "scripts" / "viventium" / "native_stack.sh"),
            "start-mongo-only",
        ],
        environment=environment,
        timeout=120,
    )
    matches = re.findall(r"^VIVENTIUM_BRIDGE_MONGO_PID=([0-9]+)$", output, re.MULTILINE)
    if len(matches) != 1:
        raise FirstUpgradeBridgeError(
            "Native MongoDB bridge did not return an exact process identity"
        )
    pid = int(matches[0])
    try:
        identity = upgrade_transaction.inspect_native_mongo_process(pid)
        dbpath = upgrade_transaction.contained(
            upgrade_transaction.native_mongo_dbpath(identity),
            context.app_support_dir,
            "native MongoDB bridge dbpath",
        )
        if (
            spec.native_executable is None
            or identity.get("executable") != str(spec.native_executable.resolve())
            or identity.get("executable_sha256") != spec.native_executable_sha256
            or identity.get("version") != spec.native_version
            or dbpath != spec.data_path
            or (
                spec.native_code_signature_verified
                and (
                    identity.get("code_signature_verified") is not True
                    or identity.get("code_signature_team_identifier")
                    != spec.native_code_signature_team_identifier
                )
            )
        ):
            raise FirstUpgradeBridgeError(
                "Native MongoDB bridge process differs from recorded predecessor identity"
            )
    except (upgrade_transaction.UpgradeTransactionError, FirstUpgradeBridgeError) as error:
        _run_checked(
            [
                str(context.repo_root / "scripts" / "viventium" / "native_stack.sh"),
                "stop-mongo-only",
                str(pid),
            ],
            environment=environment,
            timeout=60,
        )
        if isinstance(error, FirstUpgradeBridgeError):
            raise
        raise FirstUpgradeBridgeError(
            "Native MongoDB bridge process identity could not be proven"
        ) from error
    return MongoBridgeSession(
        backend=spec.backend,
        identity={"pid": matches[0], "spec": spec},
        environment=environment,
    )


def _start_docker_checkpoint_mongo(
    context: UpgradeContext,
    spec: MongoBridgeSpec,
) -> MongoBridgeSession:
    if spec.image is None:
        raise FirstUpgradeBridgeError("Recorded Docker MongoDB identity is incomplete")
    name, labels = _docker_bridge_identity(context)
    if spec.backend == "docker_named_volume":
        if spec.volume_name is None:
            raise FirstUpgradeBridgeError(
                "Recorded Docker MongoDB volume identity is incomplete"
            )
        _docker_call(["volume", "inspect", spec.volume_name])
    _docker_call(["image", "inspect", spec.image_id or spec.image])
    _remove_interrupted_docker_bridge(spec, name=name, labels=labels)
    completed = _docker_call(
        _docker_run_args(spec, name=name, labels=labels),
        timeout=600,
    )
    container_id = completed.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{12,64}", container_id):
        raise FirstUpgradeBridgeError(
            "Docker MongoDB bridge did not return an exact container identity"
        )
    inspected = _docker_inspect(container_id)
    assert inspected is not None
    _verify_docker_container(
        inspected,
        spec,
        name=name,
        labels=labels,
        expected_id=container_id,
        require_running=True,
    )
    session = MongoBridgeSession(
        backend=spec.backend,
        identity={
            "container_id": container_id,
            "name": name,
            "labels": labels,
            "spec": spec,
        },
        environment={},
    )
    readiness = [
        "container",
        "exec",
        container_id,
        "sh",
        "-ec",
        (
            "if command -v mongosh >/dev/null 2>&1; then "
            "mongosh --host 127.0.0.1 --port 27017 --quiet "
            "--eval 'quit(db.adminCommand({ping:1}).ok===1?0:2)'; "
            "elif command -v mongo >/dev/null 2>&1; then "
            "mongo --host 127.0.0.1 --port 27017 --quiet "
            "--eval 'quit(db.adminCommand({ping:1}).ok===1?0:2)'; "
            "else exit 127; fi"
        ),
    ]
    for attempt in range(60):
        if _docker_call(readiness, check=False).returncode == 0:
            return session
        if attempt < 59:
            time.sleep(1)
    _stop_checkpoint_mongo(context, session)
    raise FirstUpgradeBridgeError("Docker MongoDB bridge did not become ready")


def _start_checkpoint_mongo(
    context: UpgradeContext,
    checkpoint_runtime: Path,
) -> MongoBridgeSession:
    spec = _checkpoint_mongo_spec(context, checkpoint_runtime)
    if spec.runtime_engine == "native":
        return _start_native_checkpoint_mongo(context, spec)
    if spec.runtime_engine == "docker":
        return _start_docker_checkpoint_mongo(context, spec)
    raise FirstUpgradeBridgeError("Stopped MongoDB backend is unsupported")


def _stop_checkpoint_mongo(
    context: UpgradeContext,
    session: MongoBridgeSession,
) -> None:
    spec = session.identity.get("spec")
    if not isinstance(spec, MongoBridgeSpec) or spec.backend != session.backend:
        raise FirstUpgradeBridgeError("MongoDB bridge cleanup identity is invalid")
    if spec.runtime_engine == "native":
        pid = str(session.identity.get("pid") or "")
        if not re.fullmatch(r"[0-9]+", pid):
            raise FirstUpgradeBridgeError(
                "Native MongoDB bridge cleanup identity is invalid"
            )
        _run_checked(
            [
                str(context.repo_root / "scripts" / "viventium" / "native_stack.sh"),
                "stop-mongo-only",
                pid,
            ],
            environment=session.environment,
            timeout=60,
        )
        return
    if spec.runtime_engine == "docker":
        name = str(session.identity.get("name") or "")
        labels = session.identity.get("labels")
        container_id = str(session.identity.get("container_id") or "")
        if not isinstance(labels, dict):
            raise FirstUpgradeBridgeError(
                "Docker MongoDB bridge cleanup identity is invalid"
            )
        inspected = _docker_inspect(container_id, allow_missing=True)
        if inspected is None:
            return
        _verify_docker_container(
            inspected,
            spec,
            name=name,
            labels=labels,
            expected_id=container_id,
        )
        state = inspected.get("State")
        if isinstance(state, dict) and state.get("Running") is True:
            _docker_call(["container", "stop", "--time", "30", container_id])
        _docker_call(["container", "rm", container_id])
        if _docker_inspect(container_id, allow_missing=True) is not None:
            raise FirstUpgradeBridgeError(
                "Docker MongoDB bridge cleanup did not remove its exact container"
            )
        return
    raise FirstUpgradeBridgeError("MongoDB bridge cleanup backend is unsupported")


def _capture(
    context: UpgradeContext,
    *,
    config_file: Path,
    runtime_dir: Path,
    label: str,
    output: Path,
) -> None:
    _run_checked(
        [
            sys.executable,
            str(context.repo_root / "scripts" / "viventium" / "continuity_audit.py"),
            "capture",
            "--repo-root",
            str(context.repo_root),
            "--app-support-dir",
            str(context.app_support_dir),
            "--config-file",
            str(config_file),
            "--runtime-dir",
            str(runtime_dir),
            "--label",
            label,
            "--output",
            str(output),
        ],
        environment=_bridge_environment(),
        timeout=180,
    )


def _first_upgrade_telegram_preference_root(
    context: UpgradeContext,
) -> Path:
    canonical = context.app_support_dir / "state" / "telegram-user-configs"
    authority = (
        context.app_support_dir
        / "state"
        / "telegram-user-config-migration"
        / "authority.json"
    )
    explicit = str(
        os.environ.get("VIVENTIUM_TELEGRAM_USER_CONFIGS_DIR") or ""
    ).strip()
    if explicit:
        return lexical(Path(explicit))
    durable_candidate: Path | None = None
    owner_root = (
        context.app_support_dir
        / "state"
        / "runtime"
        / "isolated"
        / "telegram-poller"
    )
    receipts = sorted(
        owner_root.glob("owner-*.json"),
        key=lambda path: (
            path.stat().st_mtime_ns if path.is_file() else -1
        ),
        reverse=True,
    )
    for receipt in receipts:
        try:
            metadata = receipt.lstat()
            payload = json.loads(receipt.read_text(encoding="utf-8"))
            value = str(payload.get("user_configs_root") or "").strip()
            if (
                stat.S_ISREG(metadata.st_mode)
                and metadata.st_uid == os.getuid()
                and value
            ):
                durable_candidate = lexical(Path(value))
                break
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    bridge_state = (
        context.app_support_dir
        / "state"
        / "continuity"
        / "first-upgrade-bridge.json"
    )
    if (
        durable_candidate is None
        and bridge_state.is_file()
        and not bridge_state.is_symlink()
    ):
        try:
            metadata = bridge_state.lstat()
            payload = json.loads(bridge_state.read_text(encoding="utf-8"))
            telegram = payload.get("telegramContinuity")
            value = (
                str(telegram.get("effectivePreferenceRoot") or "").strip()
                if isinstance(telegram, dict)
                and telegram.get("status") == "migration-finalized"
                else ""
            )
            if (
                stat.S_ISREG(metadata.st_mode)
                and metadata.st_uid == os.getuid()
                and value
            ):
                durable_candidate = lexical(Path(value))
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    launch_script = (
        context.app_support_dir
        / "state"
        / "runtime"
        / "isolated"
        / "telegram_bot_launch.sh"
    )
    if (
        durable_candidate is None
        and launch_script.is_file()
        and not launch_script.is_symlink()
    ):
        for line in launch_script.read_text(encoding="utf-8").splitlines():
            if not line.startswith("export CONFIG_DIR="):
                continue
            try:
                words = shlex.split(line[len("export ") :])
            except ValueError:
                break
            if len(words) == 1 and words[0].startswith("CONFIG_DIR="):
                value = words[0].split("=", 1)[1]
                if value:
                    durable_candidate = lexical(Path(value))
                    break
    if (
        durable_candidate is not None
        and durable_candidate != canonical
        and not _is_legacy_telegram_preference_root(durable_candidate)
    ):
        return durable_candidate
    if authority.is_file() and not authority.is_symlink():
        return canonical
    if durable_candidate is not None:
        return durable_candidate
    telegram_root = (
        context.repo_root / "viventium_v0_4" / "telegram-viventium"
    )
    candidates = [
        telegram_root / "TelegramVivBot" / "user_configs",
        telegram_root / "user_configs",
    ]
    private_curated = str(
        os.environ.get("VIVENTIUM_PRIVATE_CURATED_DIR") or ""
    ).strip()
    private_mirror = str(
        os.environ.get("VIVENTIUM_PRIVATE_MIRROR_DIR") or ""
    ).strip()
    if private_curated:
        candidates.append(
            lexical(Path(private_curated))
            / "runtime-state"
            / "telegram-user-configs"
        )
    if private_mirror:
        candidates.append(
            lexical(Path(private_mirror))
            / "viventium_v0_4"
            / "telegram-viventium"
            / "TelegramVivBot"
            / "user_configs"
        )
    for candidate in candidates:
        if candidate.is_dir() and not candidate.is_symlink():
            return lexical(candidate)
    # The shipped predecessor treated canonical App Support as the fallback
    # only after every legacy/private candidate was absent.
    return canonical


def _is_legacy_telegram_preference_root(path: Path) -> bool:
    parts = lexical(path).parts
    suffixes = (
        (
            "viventium_v0_4",
            "telegram-viventium",
            "TelegramVivBot",
            "user_configs",
        ),
        ("viventium_v0_4", "telegram-viventium", "user_configs"),
        ("runtime-state", "telegram-user-configs"),
    )
    return any(
        len(parts) >= len(suffix)
        and tuple(parts[-len(suffix) :]) == suffix
        for suffix in suffixes
    )


def _arm_first_upgrade_telegram_continuity(
    *,
    context: UpgradeContext,
    runtime_dir: Path,
) -> dict[str, Any]:
    component_tool = (
        context.repo_root
        / "scripts"
        / "viventium"
        / "telegram_runtime_component.py"
    )
    active_root = _first_upgrade_telegram_preference_root(context)
    environment = _bridge_environment()
    candidate_selection = (
        runtime_dir / "components" / "telegram-viventium.json"
    )
    recovery_selection = (
        context.app_support_dir
        / "state"
        / "runtime-component-staging"
        / (
            "first-upgrade-telegram-recovery-"
            + hashlib.sha256(
                str(context.transaction).encode("utf-8")
            ).hexdigest()[:24]
            + ".json"
        )
    )
    for selection in (candidate_selection, recovery_selection):
        _run_checked(
            [
                sys.executable,
                str(component_tool),
                "prepare",
                "--repo-root",
                str(context.repo_root),
                "--app-support-dir",
                str(context.app_support_dir),
                "--selection-file",
                str(selection),
                "--sync-dependencies",
            ],
            environment=environment,
            timeout=1800,
        )
    _run_checked(
        [
            sys.executable,
            str(component_tool),
            "publish-recovery",
            "--app-support-dir",
            str(context.app_support_dir),
            "--selection-file",
            str(recovery_selection),
            "--transaction-kind",
            "upgrade",
            "--transaction-path",
            str(context.transaction),
            "--user-configs-root",
            str(active_root),
        ],
        environment=environment,
        timeout=120,
    )
    helper_config = context.app_support_dir / "helper-config.json"
    helper_config_before = (
        helper_config.read_bytes()
        if helper_config.is_file() and not helper_config.is_symlink()
        else None
    )
    helper_binding_matches = False
    if helper_config_before is not None:
        try:
            helper_payload = json.loads(helper_config_before)
            helper_binding_matches = (
                lexical(Path(str(helper_payload.get("repoRoot") or "")))
                == context.repo_root
                and lexical(
                    Path(str(helper_payload.get("appSupportDir") or ""))
                )
                == context.app_support_dir
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            helper_binding_matches = False
    helper_bundle = lexical(
        Path(
            os.environ.get("VIVENTIUM_HELPER_APP_BUNDLE")
            or (
                Path.home()
                / "Applications"
                / "Viventium.app"
            )
        )
    )
    helper_recovery_status = "not_installed"
    if (
        sys.platform == "darwin"
        and helper_config_before is not None
        and helper_binding_matches
        and helper_bundle.is_dir()
        and not helper_bundle.is_symlink()
    ):
        helper_environment = dict(environment)
        helper_environment["VIVENTIUM_HELPER_RECOVERY_ARM"] = "1"
        _run_checked(
            [
                str(
                    context.repo_root
                    / "scripts"
                    / "viventium"
                    / "install_macos_helper.sh"
                ),
                "install",
                "--repo-root",
                str(context.repo_root),
                "--app-support-dir",
                str(context.app_support_dir),
                "--no-launch",
                "--preserve-helper-config",
                "--recovery-bundle-only",
            ],
            environment=helper_environment,
            timeout=1200,
        )
        if helper_config.read_bytes() != helper_config_before:
            raise FirstUpgradeBridgeError(
                "First-upgrade Telegram recovery changed helper configuration"
            )
        helper_recovery_status = "armed"
    elif helper_config_before is not None and helper_bundle.exists():
        raise FirstUpgradeBridgeError(
            "Installed helper recovery binding is invalid"
        )
    return {
        "status": "rollback-armed",
        "activePreferenceRoot": str(active_root),
        "preferenceMigration": {
            "status": "deferred-until-outer-commit"
        },
        "candidateSelection": str(candidate_selection),
        "recoverySelection": str(recovery_selection),
        "helperRecovery": helper_recovery_status,
    }


def _finalize_first_upgrade_telegram_preferences(
    *,
    payload: dict[str, Any],
    repo_root: Path,
    app_support_dir: Path,
    environment: dict[str, str],
) -> Path | None:
    continuity = payload.get("telegramContinuity")
    if not isinstance(continuity, dict):
        if payload.get("receiptKind") == "current-upgrade-session":
            return None
        raise FirstUpgradeBridgeError(
            "First-upgrade Telegram continuity receipt is invalid"
        )
    if continuity.get("status") == "not_required":
        return None
    if continuity.get("status") == "migration-finalized":
        effective_value = continuity.get("effectivePreferenceRoot")
        if not isinstance(effective_value, str) or not effective_value:
            raise FirstUpgradeBridgeError(
                "Finalized Telegram preference root is missing"
            )
        effective = lexical(Path(effective_value))
        environment["VIVENTIUM_TELEGRAM_USER_CONFIGS_DIR"] = str(effective)
        return effective
    if (
        continuity.get("status") != "rollback-armed"
        or continuity.get("preferenceMigration")
        != {"status": "deferred-until-outer-commit"}
    ):
        raise FirstUpgradeBridgeError(
            "First-upgrade Telegram continuity state is unsupported"
        )
    active_value = continuity.get("activePreferenceRoot")
    if not isinstance(active_value, str) or not active_value:
        raise FirstUpgradeBridgeError(
            "First-upgrade Telegram active preference root is missing"
        )
    active = lexical(Path(active_value))
    migration_tool = (
        lexical(repo_root)
        / "scripts"
        / "viventium"
        / "telegram_user_config_migration.py"
    )
    migration_output = _run_capture(
        [
            sys.executable,
            str(migration_tool),
            "--repo-root",
            str(lexical(repo_root)),
            "--app-support-dir",
            str(lexical(app_support_dir)),
            "--active-config-root",
            str(active),
            "--writer-stopped",
        ],
        environment=environment,
        timeout=120,
    )
    try:
        migration_payload = json.loads(migration_output)
    except (TypeError, json.JSONDecodeError) as error:
        raise FirstUpgradeBridgeError(
            "First-upgrade Telegram preference migration receipt is unreadable"
        ) from error
    status = migration_payload.get("status")
    allowed_statuses = {
        "canonical-authoritative",
        "canonical-authority-initialized",
        "explicit-override-preserved",
        "migrated",
    }
    if (
        migration_payload.get("schema_version") != 2
        or status not in allowed_statuses
    ):
        raise FirstUpgradeBridgeError(
            "First-upgrade Telegram preference migration did not finalize"
        )
    canonical = lexical(app_support_dir) / "state" / "telegram-user-configs"
    effective = active if status == "explicit-override-preserved" else canonical
    continuity["status"] = "migration-finalized"
    continuity["effectivePreferenceRoot"] = str(effective)
    continuity["preferenceMigration"] = {
        key: migration_payload[key]
        for key in (
            "schema_version",
            "status",
            "changed",
            "files_changed",
            "generation",
        )
        if key in migration_payload
    }
    environment["VIVENTIUM_TELEGRAM_USER_CONFIGS_DIR"] = str(effective)
    return effective


def _validate_quiesced_upgrade_session(
    *,
    repo_root: Path,
    app_support_dir: Path,
    config_file: Path,
    runtime_dir: Path,
    lock_file: Path,
    require_successor: bool,
    state_relative: Path,
    receipt_kind: str,
) -> dict[str, Any]:
    context = load_active_context(
        repo_root=repo_root,
        app_support_dir=app_support_dir,
        required_stage="candidate_activated",
        allow_same_source=not require_successor,
    )
    if context is None:
        return {"schemaVersion": BRIDGE_SCHEMA_VERSION, "status": "not_required"}
    if require_successor:
        current_session = _load_receipt(
            context.app_support_dir,
            QUIESCED_SESSION_STATE,
        )
        if current_session is not None:
            _, current_payload = current_session
            if (
                lexical(Path(str(current_payload.get("transaction") or "")))
                == context.transaction
                and current_payload.get("status") == "validated"
                and current_payload.get("finalizedAfterOuterCommit") is False
            ):
                _load_librechat_env_checkpoint(
                    repo_root=context.repo_root,
                    transaction=context.transaction,
                    expected_manifest_sha256=(
                        _required_librechat_env_checkpoint_sha256(current_payload)
                    ),
                )
                _load_helper_config_checkpoint(
                    app_support_dir=context.app_support_dir,
                    transaction=context.transaction,
                    expected_manifest_sha256=(
                        _required_helper_config_checkpoint_sha256(current_payload)
                    ),
                )
                return current_payload
    existing_state = _load_receipt(context.app_support_dir, state_relative)
    if existing_state is not None:
        _, existing_payload = existing_state
        if (
            lexical(Path(str(existing_payload.get("transaction") or "")))
            == context.transaction
            and existing_payload.get("predecessor") == context.predecessor
            and existing_payload.get("successor") == context.successor
            and existing_payload.get("status") == "validated"
            and existing_payload.get("finalizedAfterOuterCommit") is False
        ):
            _load_librechat_env_checkpoint(
                repo_root=context.repo_root,
                transaction=context.transaction,
                expected_manifest_sha256=(
                    _required_librechat_env_checkpoint_sha256(existing_payload)
                ),
            )
            _load_helper_config_checkpoint(
                app_support_dir=context.app_support_dir,
                transaction=context.transaction,
                expected_manifest_sha256=(
                    _required_helper_config_checkpoint_sha256(existing_payload)
                ),
            )
            return existing_payload

    # The predecessor installs the downloaded helper only after its outer
    # transaction commits. Verify the exact shipped successor artifact before
    # accepting the candidate so a stale/corrupt prebuilt cannot turn a healthy
    # core commit into an unrecoverable post-commit helper mismatch.
    _run_checked(
        [
            sys.executable,
            str(
                context.repo_root
                / "scripts"
                / "viventium"
                / "helper_artifact_verify.py"
            ),
            "--package-dir",
            str(context.repo_root / "apps" / "macos" / "ViventiumHelper"),
        ],
        environment=_bridge_environment(),
        timeout=60,
    )

    bridge_dir = context.transaction / "successor-bridge"
    bridge_dir.mkdir(mode=0o700, exist_ok=True)
    librechat_env_checkpoint = _checkpoint_librechat_env(context)
    librechat_env_checkpoint_sha256 = sha256_file(
        librechat_env_checkpoint["manifestPath"]
    )
    helper_config_checkpoint = _checkpoint_helper_config(context)
    helper_config_checkpoint_sha256 = sha256_file(
        helper_config_checkpoint["manifestPath"]
    )
    telegram_continuity: dict[str, Any] = {"status": "not_required"}
    if require_successor:
        telegram_continuity = _arm_first_upgrade_telegram_continuity(
            context=context,
            runtime_dir=lexical(runtime_dir),
        )
    baseline = bridge_dir / "stopped-baseline.json"
    live = bridge_dir / "validated-live.json"
    comparison = bridge_dir / "strict-comparison.json"
    checkpoint_config = _surface_backup(context, "config")
    checkpoint_runtime = _surface_backup(context, "runtime")

    mongo_session = _start_checkpoint_mongo(context, checkpoint_runtime)
    try:
        _capture(
            context,
            config_file=checkpoint_config,
            runtime_dir=checkpoint_runtime,
            label="successor-bridge-stopped-baseline",
            output=baseline,
        )
    finally:
        # No candidate worker may start until the ledger-bound baseline
        # MongoDB is stopped and its exact process/container identity is gone.
        _stop_checkpoint_mongo(context, mongo_session)
    _run_checked(
        [
            str(context.repo_root / "bin" / "viventium"),
            "--app-support-dir",
            str(context.app_support_dir),
            "--config-file",
            str(config_file),
            "--runtime-dir",
            str(runtime_dir),
            "--lock-file",
            str(lock_file),
            "_first-upgrade-runtime",
            "start-quiesced-and-wait",
        ],
        environment=_bridge_environment(),
        timeout=int(os.environ.get("VIVENTIUM_FIRST_UPGRADE_BRIDGE_TIMEOUT_SECONDS", "2100")),
    )
    _capture(
        context,
        config_file=config_file,
        runtime_dir=runtime_dir,
        label="successor-bridge-validated-live",
        output=live,
    )
    _run_checked(
        [
            sys.executable,
            str(context.repo_root / "scripts" / "viventium" / "continuity_audit.py"),
            "compare",
            "--snapshot-manifest",
            str(baseline),
            "--live-manifest",
            str(live),
            "--strict-semantic",
            "--output",
            str(comparison),
        ],
        environment=_bridge_environment(),
        timeout=60,
    )
    comparison_payload = json.loads(comparison.read_text(encoding="utf-8"))
    if comparison_payload.get("status") != "ok":
        raise FirstUpgradeBridgeError("Successor runtime changed protected user state")
    quiesced_librechat_env_proof = _verify_librechat_env_after_full_start(
        repo_root=context.repo_root,
        transaction=context.transaction,
        expected_manifest_sha256=librechat_env_checkpoint_sha256,
    )
    quiesced_helper_config_proof = _verify_helper_config_after_full_start(
        app_support_dir=context.app_support_dir,
        transaction=context.transaction,
        expected_manifest_sha256=helper_config_checkpoint_sha256,
    )

    canonical_uploads = context.app_support_dir / "data" / "uploads"
    legacy_uploads = (
        context.repo_root / "viventium_v0_4" / "LibreChat" / "uploads"
    )
    uploads_deferred = (
        not canonical_uploads.exists()
        and not canonical_uploads.is_symlink()
        and legacy_uploads.is_dir()
        and not legacy_uploads.is_symlink()
    )
    payload = {
        "schemaVersion": BRIDGE_SCHEMA_VERSION,
        "receiptKind": receipt_kind,
        "status": "validated",
        "transaction": str(context.transaction),
        "predecessor": context.predecessor,
        "successor": context.successor,
        "wasRunning": context.was_running,
        "uploadsDeferredUntilOuterCommit": uploads_deferred,
        "baselineSha256": sha256_file(baseline),
        "liveSha256": sha256_file(live),
        "comparisonSha256": sha256_file(comparison),
        "librechatEnvCheckpointSha256": librechat_env_checkpoint_sha256,
        "quiescedLibreChatEnvContinuity": quiesced_librechat_env_proof,
        "helperConfigCheckpointSha256": helper_config_checkpoint_sha256,
        "quiescedHelperConfigContinuity": quiesced_helper_config_proof,
        "telegramContinuity": telegram_continuity,
        "disabledWriters": SUCCESSOR_VALIDATION_DISABLED_WRITERS,
        "postCommitFinalizationId": postcommit_finalization_id(
            context.transaction,
            context.successor,
        ),
        "finalizedAfterOuterCommit": False,
    }
    write_private_json(
        bridge_dir / "receipt.json",
        payload,
        boundary=context.transaction,
    )
    write_private_json(
        context.app_support_dir / state_relative,
        payload,
        boundary=context.app_support_dir,
    )
    return payload


def validate_first_hop(
    *,
    repo_root: Path,
    app_support_dir: Path,
    config_file: Path,
    runtime_dir: Path,
    lock_file: Path,
) -> dict[str, Any]:
    return _validate_quiesced_upgrade_session(
        repo_root=repo_root,
        app_support_dir=app_support_dir,
        config_file=config_file,
        runtime_dir=runtime_dir,
        lock_file=lock_file,
        require_successor=True,
        state_relative=BRIDGE_STATE,
        receipt_kind="first-upgrade-successor",
    )


def validate_current_upgrade_session(
    *,
    repo_root: Path,
    app_support_dir: Path,
    config_file: Path,
    runtime_dir: Path,
    lock_file: Path,
) -> dict[str, Any]:
    return _validate_quiesced_upgrade_session(
        repo_root=repo_root,
        app_support_dir=app_support_dir,
        config_file=config_file,
        runtime_dir=runtime_dir,
        lock_file=lock_file,
        require_successor=False,
        state_relative=QUIESCED_SESSION_STATE,
        receipt_kind="current-upgrade-session",
    )


def _load_receipt(
    app_support_dir: Path,
    state_relative: Path,
) -> tuple[Path, dict[str, Any]] | None:
    path = lexical(app_support_dir) / state_relative
    if not path.exists() and not path.is_symlink():
        return None
    upgrade_transaction.validate_chain(path, owned_from=lexical(app_support_dir))
    metadata = path.lstat()
    if path.is_symlink() or not path.is_file() or metadata.st_uid != os.getuid():
        raise FirstUpgradeBridgeError("Quiesced upgrade session receipt is unsafe")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != BRIDGE_SCHEMA_VERSION:
        raise FirstUpgradeBridgeError(
            "Quiesced upgrade session receipt schema is unsupported"
        )
    return path, payload


def _load_bridge_state(app_support_dir: Path) -> tuple[Path, dict[str, Any]] | None:
    return _load_receipt(app_support_dir, BRIDGE_STATE)


def inspect_active_quiesced_receipt(
    *,
    repo_root: Path,
    app_support_dir: Path,
) -> dict[str, Any]:
    state = _load_receipt(app_support_dir, QUIESCED_SESSION_STATE)
    if state is None:
        state = _load_bridge_state(app_support_dir)
    if state is None:
        return {"schemaVersion": BRIDGE_SCHEMA_VERSION, "status": "inactive"}
    _, payload = state
    if (
        payload.get("status") != "validated"
        or payload.get("finalizedAfterOuterCommit") is not False
    ):
        return {"schemaVersion": BRIDGE_SCHEMA_VERSION, "status": "inactive"}
    if payload.get("disabledWriters") != SUCCESSOR_VALIDATION_DISABLED_WRITERS:
        raise FirstUpgradeBridgeError(
            "Active successor validation writer inventory is incomplete"
        )
    transaction = lexical(Path(str(payload.get("transaction") or "")))
    try:
        ledger = upgrade_transaction.load_ledger(transaction)
    except upgrade_transaction.UpgradeTransactionError as error:
        raise FirstUpgradeBridgeError(
            "Active quiesced successor transaction proof failed"
        ) from error
    resolved_repo = lexical(repo_root)
    if (
        ledger.get("status") != "active"
        or lexical(Path(str(ledger.get("repo_root") or ""))) != resolved_repo
        or lexical(Path(str(ledger.get("app_support_dir") or "")))
        != lexical(app_support_dir)
        or payload.get("successor") != git_text(resolved_repo, "rev-parse", "HEAD")
    ):
        raise FirstUpgradeBridgeError(
            "Active quiesced successor receipt does not match this runtime"
        )
    return {
        "schemaVersion": BRIDGE_SCHEMA_VERSION,
        "status": "active",
        "disabledWriters": SUCCESSOR_VALIDATION_DISABLED_WRITERS,
    }


def inspect_pending_postcommit_finalization(
    *,
    repo_root: Path,
    app_support_dir: Path,
) -> dict[str, Any]:
    state = _load_receipt(app_support_dir, QUIESCED_SESSION_STATE)
    if state is None:
        state = _load_bridge_state(app_support_dir)
    if state is None:
        return {"schemaVersion": BRIDGE_SCHEMA_VERSION, "status": "inactive"}
    _, payload = state
    if (
        payload.get("status") != "pending_first_start"
        or payload.get("finalizedAfterOuterCommit") is not False
        or payload.get("wasRunning") is not False
    ):
        return {"schemaVersion": BRIDGE_SCHEMA_VERSION, "status": "inactive"}
    transaction = lexical(Path(str(payload.get("transaction") or "")))
    try:
        ledger = upgrade_transaction.load_ledger(transaction)
    except upgrade_transaction.UpgradeTransactionError as error:
        raise FirstUpgradeBridgeError(
            "Pending post-commit finalization transaction proof failed"
        ) from error
    resolved_repo = lexical(repo_root)
    resolved_support = lexical(app_support_dir)
    source_id = str(payload.get("successor") or "")
    expected_run_id = postcommit_finalization_id(transaction, source_id)
    if (
        ledger.get("status") != "committed"
        or lexical(Path(str(ledger.get("repo_root") or ""))) != resolved_repo
        or lexical(Path(str(ledger.get("app_support_dir") or "")))
        != resolved_support
        or source_id != git_text(resolved_repo, "rev-parse", "HEAD")
        or payload.get("postCommitFinalizationId") != expected_run_id
    ):
        raise FirstUpgradeBridgeError(
            "Pending post-commit finalization does not match this runtime"
        )
    return {
        "schemaVersion": BRIDGE_SCHEMA_VERSION,
        "status": "pending",
        "runId": expected_run_id,
        "sourceId": source_id,
        "telegramPreferenceRoot": (
            payload.get("telegramContinuity", {}).get(
                "effectivePreferenceRoot"
            )
            if isinstance(payload.get("telegramContinuity"), dict)
            and payload.get("telegramContinuity", {}).get("status")
            == "migration-finalized"
            else ""
        ),
    }


def _stop_runtime_for_continuity_recovery(
    *,
    context_repo: Path,
    app_support_dir: Path,
    config_file: Path,
    runtime_dir: Path,
    lock_file: Path,
    environment: dict[str, str],
    deferred_first_start: bool,
) -> None:
    command = [
        str(context_repo / "bin" / "viventium"),
        "--app-support-dir",
        str(app_support_dir),
        "--config-file",
        str(config_file),
        "--runtime-dir",
        str(runtime_dir),
        "--lock-file",
        str(lock_file),
    ]
    if deferred_first_start:
        # The original upgrade lock no longer exists on a later user start.
        # Use the ordinary owner-scoped stop path and fail closed rather than
        # forging inherited-lock authority.
        clean_environment = environment.copy()
        for name in (
            "VIVENTIUM_CLI_LOCK_HELD",
            "VIVENTIUM_CLI_LOCK_DIR",
            "VIVENTIUM_CLI_LOCK_OWNER_PID",
            "VIVENTIUM_CLI_LOCK_INHERITED_ONCE",
        ):
            clean_environment.pop(name, None)
        _run_checked(
            [*command, "stop"],
            environment=clean_environment,
            timeout=300,
        )
        return
    _run_checked(
        [*command, "_first-upgrade-runtime", "restore-stopped"],
        environment=environment,
        timeout=300,
    )


def finalize_after_outer_commit(
    *,
    repo_root: Path,
    app_support_dir: Path,
    config_file: Path,
    runtime_dir: Path,
    lock_file: Path,
    state_relative: Path = BRIDGE_STATE,
    require_deferred_ready: bool = False,
) -> dict[str, Any]:
    state = _load_receipt(app_support_dir, state_relative)
    if state is None:
        return {"schemaVersion": BRIDGE_SCHEMA_VERSION, "status": "not_required"}
    state_path, payload = state
    if payload.get("finalizedAfterOuterCommit") is True:
        if payload.get("privateCheckpointCleanupComplete") is not True:
            transaction = _validated_committed_cleanup_transaction(
                transaction=Path(str(payload.get("transaction") or "")),
                app_support_dir=app_support_dir,
                repo_root=repo_root,
            )
            payload["privateCheckpointCleanupComplete"] = (
                _cleanup_successor_private_checkpoints(transaction)
            )
            payload["status"] = (
                "finalized"
                if payload["privateCheckpointCleanupComplete"]
                else "finalized_private_cleanup_pending"
            )
            write_private_json(
                state_path,
                payload,
                boundary=lexical(app_support_dir),
            )
        return payload
    if (
        payload.get("status") == "pending_first_start"
        and payload.get("wasRunning") is False
        and not require_deferred_ready
        and (
            payload.get("receiptKind") == "current-upgrade-session"
            or (
                isinstance(payload.get("telegramContinuity"), dict)
                and payload.get("telegramContinuity", {}).get("status")
                == "migration-finalized"
            )
        )
    ):
        return payload
    transaction = lexical(Path(str(payload.get("transaction") or "")))
    try:
        ledger = upgrade_transaction.load_ledger(transaction)
    except upgrade_transaction.UpgradeTransactionError as error:
        raise FirstUpgradeBridgeError("Committed outer transaction proof failed") from error
    if ledger.get("status") == "rolled_back":
        payload["finalizedAfterOuterCommit"] = False
        payload["status"] = "rolled_back"
        write_private_json(state_path, payload, boundary=lexical(app_support_dir))
        return payload
    if ledger.get("status") != "committed":
        raise FirstUpgradeBridgeError("Outer upgrade transaction is not committed")
    context_repo = lexical(Path(str(ledger.get("repo_root") or "")))
    if context_repo != lexical(repo_root):
        raise FirstUpgradeBridgeError("Committed bridge receipt belongs to another checkout")
    librechat_env_checkpoint_sha256 = (
        _required_librechat_env_checkpoint_sha256(payload)
    )
    helper_config_checkpoint_sha256 = (
        _required_helper_config_checkpoint_sha256(payload)
    )
    expected_finalization_id = postcommit_finalization_id(
        transaction,
        str(payload.get("successor") or ""),
    )
    recorded_finalization_id = payload.get("postCommitFinalizationId")
    if recorded_finalization_id not in (None, expected_finalization_id):
        raise FirstUpgradeBridgeError(
            "Committed bridge post-commit finalization identity changed"
        )
    payload["postCommitFinalizationId"] = expected_finalization_id

    environment = _bridge_environment()
    environment["VIVENTIUM_POSTCOMMIT_FINALIZATION_ID"] = (
        expected_finalization_id
    )
    environment["VIVENTIUM_POSTCOMMIT_SOURCE_ID"] = str(
        payload.get("successor") or ""
    )
    was_running = bool(payload.get("wasRunning"))
    stopped_first_start_ready = (
        not was_running
        and payload.get("status") == "pending_first_start"
        and payload.get("postCommitApiFinalization", {}).get("status")
        == "pending-first-start"
    )
    if stopped_first_start_ready:
        try:
            payload["postCommitApiFinalization"] = (
                _verify_postcommit_api_finalization(
                    app_support_dir=app_support_dir,
                    run_id=expected_finalization_id,
                    source_id=str(payload.get("successor") or ""),
                )
            )
        except FirstUpgradeBridgeError:
            _stop_runtime_for_continuity_recovery(
                context_repo=context_repo,
                app_support_dir=app_support_dir,
                config_file=config_file,
                runtime_dir=runtime_dir,
                lock_file=lock_file,
                environment=environment,
                deferred_first_start=True,
            )
            raise
    # Keep the successor passive through the predecessor/current controller's
    # outer post-capture, strict comparison, and commit. Only a committed ledger
    # may replace that quiesced process with the configured runtime.
    if not stopped_first_start_ready:
        _stop_runtime_for_continuity_recovery(
            context_repo=context_repo,
            app_support_dir=app_support_dir,
            config_file=config_file,
            runtime_dir=runtime_dir,
            lock_file=lock_file,
            environment=environment,
            deferred_first_start=stopped_first_start_ready,
        )
    effective_telegram_root = _finalize_first_upgrade_telegram_preferences(
        payload=payload,
        repo_root=context_repo,
        app_support_dir=app_support_dir,
        environment=environment,
    )
    if effective_telegram_root is not None:
        # Persist the authority handoff before any configured writer may start.
        # A crash after this point resumes from this exact effective root.
        write_private_json(
            state_path,
            payload,
            boundary=lexical(app_support_dir),
        )
    if payload.get("uploadsDeferredUntilOuterCommit"):
        try:
            _run_checked(
                [
                    sys.executable,
                    str(context_repo / "scripts" / "viventium" / "uploads_migration.py"),
                    "--app-support-dir",
                    str(app_support_dir),
                    "--librechat-dir",
                    str(context_repo / "viventium_v0_4" / "LibreChat"),
                    "--canonical-root",
                    str(lexical(app_support_dir) / "data" / "uploads"),
                ],
                environment=environment,
                timeout=1800,
            )
        except Exception:
            if was_running:
                _run_checked(
                    [
                        str(context_repo / "bin" / "viventium"),
                        "--app-support-dir",
                        str(app_support_dir),
                        "--config-file",
                        str(config_file),
                        "--runtime-dir",
                        str(runtime_dir),
                        "--lock-file",
                        str(lock_file),
                        "_first-upgrade-runtime",
                        "start-full-and-wait",
                    ],
                    environment=environment,
                    timeout=int(
                        os.environ.get(
                            "VIVENTIUM_FIRST_UPGRADE_BRIDGE_TIMEOUT_SECONDS",
                            "2100",
                        )
                    ),
                )
            raise
    if was_running:
        _run_checked(
            [
                str(context_repo / "bin" / "viventium"),
                "--app-support-dir",
                str(app_support_dir),
                "--config-file",
                str(config_file),
                "--runtime-dir",
                str(runtime_dir),
                "--lock-file",
                str(lock_file),
                "_first-upgrade-runtime",
                "start-full-and-wait",
            ],
            environment=environment,
            timeout=int(
                os.environ.get(
                    "VIVENTIUM_FIRST_UPGRADE_BRIDGE_TIMEOUT_SECONDS",
                    "2100",
                )
            ),
        )
        payload["postCommitApiFinalization"] = (
            _verify_postcommit_api_finalization(
                app_support_dir=app_support_dir,
                run_id=expected_finalization_id,
                source_id=str(payload.get("successor") or ""),
            )
        )
    elif not stopped_first_start_ready:
        payload["postCommitApiFinalization"] = {
            "status": "pending-first-start"
        }
    try:
        payload["librechatEnvContinuity"] = (
            _verify_librechat_env_after_full_start(
                repo_root=context_repo,
                transaction=transaction,
                expected_manifest_sha256=librechat_env_checkpoint_sha256,
            )
        )
    except FirstUpgradeBridgeError:
        payload["finalizedAfterOuterCommit"] = False
        payload["status"] = "librechat_env_recovery_required"
        write_private_json(state_path, payload, boundary=lexical(app_support_dir))
        _stop_runtime_for_continuity_recovery(
            context_repo=context_repo,
            app_support_dir=app_support_dir,
            config_file=config_file,
            runtime_dir=runtime_dir,
            lock_file=lock_file,
            environment=environment,
            deferred_first_start=stopped_first_start_ready,
        )
        _restore_librechat_env_checkpoint(
            repo_root=context_repo,
            transaction=transaction,
            expected_manifest_sha256=librechat_env_checkpoint_sha256,
        )
        payload["librechatEnvRecoveredFromCheckpoint"] = True
        payload["status"] = "librechat_env_recovered"
        write_private_json(state_path, payload, boundary=lexical(app_support_dir))
        raise
    try:
        payload["helperConfigContinuity"] = (
            _verify_helper_config_after_full_start(
                app_support_dir=app_support_dir,
                transaction=transaction,
                expected_manifest_sha256=helper_config_checkpoint_sha256,
            )
        )
    except FirstUpgradeBridgeError:
        payload["finalizedAfterOuterCommit"] = False
        payload["status"] = "helper_config_recovery_required"
        write_private_json(state_path, payload, boundary=lexical(app_support_dir))
        _stop_runtime_for_continuity_recovery(
            context_repo=context_repo,
            app_support_dir=app_support_dir,
            config_file=config_file,
            runtime_dir=runtime_dir,
            lock_file=lock_file,
            environment=environment,
            deferred_first_start=stopped_first_start_ready,
        )
        _restore_helper_config_checkpoint(
            app_support_dir=app_support_dir,
            transaction=transaction,
            expected_manifest_sha256=helper_config_checkpoint_sha256,
        )
        payload["helperConfigRecoveredFromCheckpoint"] = True
        payload["status"] = "helper_config_recovered"
        write_private_json(state_path, payload, boundary=lexical(app_support_dir))
        raise
    fully_finalized = was_running or stopped_first_start_ready
    payload["finalizedAfterOuterCommit"] = fully_finalized
    payload["status"] = "finalized" if fully_finalized else "pending_first_start"
    write_private_json(state_path, payload, boundary=lexical(app_support_dir))
    if fully_finalized:
        transaction = _validated_committed_cleanup_transaction(
            transaction=transaction,
            app_support_dir=app_support_dir,
            repo_root=repo_root,
        )
        payload["privateCheckpointCleanupComplete"] = (
            _cleanup_successor_private_checkpoints(transaction)
        )
        if not payload["privateCheckpointCleanupComplete"]:
            payload["status"] = "finalized_private_cleanup_pending"
        write_private_json(state_path, payload, boundary=lexical(app_support_dir))
    return payload


def finalize_pending_after_first_start(
    *,
    repo_root: Path,
    app_support_dir: Path,
    config_file: Path,
    runtime_dir: Path,
    lock_file: Path,
) -> dict[str, Any]:
    selected: Path | None = None
    for candidate in (QUIESCED_SESSION_STATE, BRIDGE_STATE):
        state = _load_receipt(app_support_dir, candidate)
        if state is None:
            continue
        _, payload = state
        if (
            payload.get("status") == "pending_first_start"
            and payload.get("finalizedAfterOuterCommit") is False
            and payload.get("wasRunning") is False
        ):
            if selected is not None:
                raise FirstUpgradeBridgeError(
                    "Pending post-commit finalization receipt is ambiguous"
                )
            selected = candidate
    if selected is None:
        return {"schemaVersion": BRIDGE_SCHEMA_VERSION, "status": "not_required"}
    return finalize_after_outer_commit(
        repo_root=repo_root,
        app_support_dir=app_support_dir,
        config_file=config_file,
        runtime_dir=runtime_dir,
        lock_file=lock_file,
        state_relative=selected,
        require_deferred_ready=True,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in (
        "validate",
        "validate-session",
        "finalize-after-commit",
        "finalize-session-after-commit",
        "finalize-pending-after-first-start",
        "active-quiesced",
        "pending-postcommit",
    ):
        child = subparsers.add_parser(command)
        child.add_argument("--repo-root", type=Path, required=True)
        child.add_argument("--app-support-dir", type=Path, required=True)
        if command not in {"active-quiesced", "pending-postcommit"}:
            child.add_argument("--config-file", type=Path, required=True)
            child.add_argument("--runtime-dir", type=Path, required=True)
            child.add_argument("--lock-file", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            result = validate_first_hop(
                repo_root=args.repo_root,
                app_support_dir=args.app_support_dir,
                config_file=args.config_file,
                runtime_dir=args.runtime_dir,
                lock_file=args.lock_file,
            )
        elif args.command == "validate-session":
            result = validate_current_upgrade_session(
                repo_root=args.repo_root,
                app_support_dir=args.app_support_dir,
                config_file=args.config_file,
                runtime_dir=args.runtime_dir,
                lock_file=args.lock_file,
            )
        elif args.command in {
            "finalize-after-commit",
            "finalize-session-after-commit",
            "finalize-pending-after-first-start",
        }:
            if args.command == "finalize-pending-after-first-start":
                result = finalize_pending_after_first_start(
                    repo_root=args.repo_root,
                    app_support_dir=args.app_support_dir,
                    config_file=args.config_file,
                    runtime_dir=args.runtime_dir,
                    lock_file=args.lock_file,
                )
            else:
                result = finalize_after_outer_commit(
                    repo_root=args.repo_root,
                    app_support_dir=args.app_support_dir,
                    config_file=args.config_file,
                    runtime_dir=args.runtime_dir,
                    lock_file=args.lock_file,
                    state_relative=(
                        QUIESCED_SESSION_STATE
                        if args.command == "finalize-session-after-commit"
                        else BRIDGE_STATE
                    ),
                )
        elif args.command == "active-quiesced":
            result = inspect_active_quiesced_receipt(
                repo_root=args.repo_root,
                app_support_dir=args.app_support_dir,
            )
        else:
            result = inspect_pending_postcommit_finalization(
                repo_root=args.repo_root,
                app_support_dir=args.app_support_dir,
            )
    except (
        FirstUpgradeBridgeError,
        upgrade_support.UpgradeSupportError,
        json.JSONDecodeError,
        OSError,
        subprocess.SubprocessError,
        ValueError,
    ) as error:
        print(f"Viventium first-upgrade bridge failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
