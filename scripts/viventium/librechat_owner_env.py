#!/usr/bin/env python3
"""Safely carry an owner-managed LibreChat environment across checkout promotion."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import upgrade_transaction  # noqa: E402


MANIFEST_KIND = "librechat-owner-environment-continuity"
GIT_COMMIT = re.compile(r"[0-9a-f]{40,64}")


class OwnerEnvError(RuntimeError):
    pass


def _lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def _owned_regular_snapshot(path: Path) -> tuple[bytes, dict[str, int]]:
    path = _lexical(path)
    upgrade_transaction.validate_chain(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise OwnerEnvError("LibreChat owner environment could not be opened safely") from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid():
            raise OwnerEnvError(
                "LibreChat owner environment is not a current-user-owned regular file"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            contents = handle.read()
        after = os.fstat(descriptor)
        if (
            before.st_dev != after.st_dev
            or before.st_ino != after.st_ino
            or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or len(contents) != after.st_size
        ):
            raise OwnerEnvError("LibreChat owner environment changed while it was read")
        binding = {
            "device": after.st_dev,
            "inode": after.st_ino,
            "size": after.st_size,
            "mtime_ns": after.st_mtime_ns,
        }
        return contents, binding
    finally:
        os.close(descriptor)


def _validate_repo_env(repo: Path, env_file: Path) -> tuple[Path, Path]:
    repo = _lexical(repo)
    env_file = _lexical(env_file)
    expected = repo / "viventium_v0_4" / "LibreChat" / ".env"
    if env_file != expected:
        raise OwnerEnvError("LibreChat target environment is outside the candidate checkout")
    upgrade_transaction.validate_chain(repo)
    metadata = repo.lstat()
    if repo.is_symlink() or not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
        raise OwnerEnvError("Candidate checkout is not a current-user-owned safe directory")
    parent = env_file.parent
    upgrade_transaction.validate_chain(parent, owned_from=repo)
    parent_metadata = parent.lstat()
    if (
        parent.is_symlink()
        or not stat.S_ISDIR(parent_metadata.st_mode)
        or parent_metadata.st_uid != os.getuid()
    ):
        raise OwnerEnvError("Candidate LibreChat directory is unsafe")
    if env_file.exists() or env_file.is_symlink():
        target_metadata = env_file.lstat()
        if (
            env_file.is_symlink()
            or not stat.S_ISREG(target_metadata.st_mode)
            or target_metadata.st_uid != os.getuid()
        ):
            raise OwnerEnvError("Candidate LibreChat owner environment is unsafe")
    return repo, env_file


def _validate_commit(commit: str) -> str:
    if not GIT_COMMIT.fullmatch(commit):
        raise OwnerEnvError("Candidate checkout commit binding is invalid")
    return commit


def _current_nested_commit(repo: Path) -> str:
    git = shutil.which("git")
    if not git:
        raise OwnerEnvError("Git is required to bind the candidate LibreChat revision")
    try:
        completed = subprocess.run(
            [git, "-C", str(repo / "viventium_v0_4" / "LibreChat"), "rev-parse", "--verify", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise OwnerEnvError("Candidate LibreChat revision could not be verified") from error
    commit = completed.stdout.strip()
    if completed.returncode != 0 or not GIT_COMMIT.fullmatch(commit):
        raise OwnerEnvError("Candidate LibreChat revision could not be verified")
    return commit


def _repo_digest(repo: Path) -> str:
    return hashlib.sha256(str(_lexical(repo)).encode("utf-8")).hexdigest()


def _validate_destination(runtime_dir: Path, destination: Path) -> Path:
    runtime_dir = _lexical(runtime_dir)
    destination = _lexical(destination)
    expected = runtime_dir / "service-env" / "librechat.owner.env"
    if destination != expected:
        raise OwnerEnvError(
            "LibreChat owner environment destination is outside the candidate runtime"
        )
    upgrade_transaction.validate_chain(runtime_dir)
    if not runtime_dir.is_dir() or runtime_dir.is_symlink():
        raise OwnerEnvError("Candidate runtime is not a safe directory")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    upgrade_transaction.validate_chain(destination.parent, owned_from=runtime_dir)
    if destination.exists() or destination.is_symlink():
        metadata = destination.lstat()
        if (
            destination.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
        ):
            raise OwnerEnvError("Candidate LibreChat owner environment is unsafe")
    return destination


def _atomic_write(path: Path, contents: bytes, mode: int = 0o600) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def _load_manifest(manifest: Path) -> dict[str, Any]:
    contents, _ = _owned_regular_snapshot(manifest)
    try:
        payload = json.loads(contents)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OwnerEnvError("LibreChat owner environment manifest is invalid") from error
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 2
        or payload.get("kind") != MANIFEST_KIND
        or not isinstance(payload.get("semantic_manifest"), dict)
        or not isinstance(payload.get("source_binding"), dict)
        or not isinstance(payload.get("target_binding"), dict)
    ):
        raise OwnerEnvError("LibreChat owner environment manifest is invalid")
    return payload


def _validate_target_binding(
    payload: dict[str, Any],
    target_repo: Path,
    target_commit: str,
) -> None:
    target_commit = _validate_commit(target_commit)
    current_commit = _current_nested_commit(target_repo)
    binding = payload["target_binding"]
    if (
        binding.get("repo_sha256") != _repo_digest(target_repo)
        or binding.get("git_commit") != target_commit
        or current_commit != target_commit
    ):
        raise OwnerEnvError("LibreChat owner snapshot belongs to another checkout revision")


def _snapshot_proof(payload: dict[str, Any], snapshot: Path) -> tuple[bytes, dict[str, Any]]:
    contents, _ = _owned_regular_snapshot(snapshot)
    semantic = upgrade_transaction.librechat_env_semantic_manifest_from_bytes(contents)
    expected = payload["semantic_manifest"]
    if (
        semantic.get("file_sha256") != expected.get("file_sha256")
        or semantic != expected
    ):
        raise OwnerEnvError("LibreChat owner snapshot does not match its manifest")
    return contents, semantic


def _target_precondition(target: Path) -> dict[str, Any]:
    if not target.exists() and not target.is_symlink():
        return {"exists": False, "file_sha256": ""}
    contents, _ = _owned_regular_snapshot(target)
    semantic = upgrade_transaction.librechat_env_semantic_manifest_from_bytes(contents)
    return {
        "exists": True,
        "file_sha256": semantic["file_sha256"],
    }


def _verify_target_precondition(payload: dict[str, Any], target: Path) -> None:
    expected = payload.get("target_precondition")
    if not isinstance(expected, dict):
        raise OwnerEnvError("LibreChat owner snapshot target precondition is missing")
    actual = _target_precondition(target)
    if actual != expected:
        raise OwnerEnvError(
            "Candidate LibreChat environment changed after activation checkpoint"
        )


def _read_owned_regular_descriptor(descriptor: int) -> tuple[bytes, os.stat_result]:
    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid():
        raise OwnerEnvError(
            "Candidate LibreChat environment is not a current-user-owned regular file"
        )
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            break
        chunks.append(chunk)
    contents = b"".join(chunks)
    after = os.fstat(descriptor)
    if (
        before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or before.st_ctime_ns != after.st_ctime_ns
        or len(contents) != after.st_size
    ):
        raise OwnerEnvError("Candidate LibreChat environment changed while it was read")
    return contents, after


def _materialize_with_precondition(
    payload: dict[str, Any],
    target: Path,
    contents: bytes,
) -> None:
    expected = payload.get("target_precondition")
    if not isinstance(expected, dict) or not isinstance(expected.get("exists"), bool):
        raise OwnerEnvError("LibreChat owner snapshot target precondition is missing")
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    directory_descriptor = os.open(target.parent, directory_flags)
    try:
        materialized_name = payload.get("materialization_target_name")
        if (
            not isinstance(materialized_name, str)
            or not materialized_name.startswith(".env.viventium-materialized-")
            or "/" in materialized_name
        ):
            raise OwnerEnvError(
                "LibreChat materialization target identity is invalid"
            )
        if expected["exists"]:
            descriptor = os.open(
                target.name,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=directory_descriptor,
            )
            try:
                current, read_metadata = _read_owned_regular_descriptor(descriptor)
            finally:
                os.close(descriptor)
            path_metadata = os.stat(
                target.name,
                dir_fd=directory_descriptor,
                follow_symlinks=False,
            )
            if (
                read_metadata.st_dev != path_metadata.st_dev
                or read_metadata.st_ino != path_metadata.st_ino
                or read_metadata.st_size != path_metadata.st_size
                or read_metadata.st_mtime_ns != path_metadata.st_mtime_ns
                or read_metadata.st_ctime_ns != path_metadata.st_ctime_ns
                or hashlib.sha256(current).hexdigest()
                != expected.get("file_sha256")
            ):
                raise OwnerEnvError(
                    "Candidate LibreChat environment changed during materialization"
                )
            if current != contents:
                raise OwnerEnvError(
                    "Candidate checkout has an independent LibreChat owner "
                    "environment; activation will not overwrite it"
                )
            try:
                os.link(
                    target.name,
                    materialized_name,
                    src_dir_fd=directory_descriptor,
                    dst_dir_fd=directory_descriptor,
                    follow_symlinks=False,
                )
            except FileExistsError as error:
                raise OwnerEnvError(
                    "Candidate LibreChat materialization target is incomplete"
                ) from error

        else:
            try:
                descriptor = os.open(
                    materialized_name,
                    os.O_WRONLY
                    | os.O_CREAT
                    | os.O_EXCL
                    | getattr(os, "O_NOFOLLOW", 0),
                    0o600,
                    dir_fd=directory_descriptor,
                )
            except FileExistsError:
                descriptor = os.open(
                    materialized_name,
                    os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=directory_descriptor,
                )
                try:
                    existing, _ = _read_owned_regular_descriptor(descriptor)
                finally:
                    os.close(descriptor)
                if existing != contents:
                    raise OwnerEnvError(
                        "Candidate LibreChat materialization target is incomplete"
                    )
            else:
                try:
                    view = memoryview(contents)
                    while view:
                        written = os.write(descriptor, view)
                        if written <= 0:
                            raise OwnerEnvError(
                                "Candidate LibreChat environment could not be materialized"
                            )
                        view = view[written:]
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            try:
                os.link(
                    materialized_name,
                    target.name,
                    src_dir_fd=directory_descriptor,
                    dst_dir_fd=directory_descriptor,
                    follow_symlinks=False,
                )
            except FileExistsError as error:
                raise OwnerEnvError(
                    "Candidate LibreChat environment changed during materialization"
                ) from error
        os.fsync(directory_descriptor)
        try:
            materialized_descriptor = os.open(
                materialized_name,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=directory_descriptor,
            )
            try:
                materialized_contents, materialized_metadata = (
                    _read_owned_regular_descriptor(materialized_descriptor)
                )
            finally:
                os.close(materialized_descriptor)
            target_metadata = os.stat(
                target.name,
                dir_fd=directory_descriptor,
                follow_symlinks=False,
            )
            if (
                materialized_metadata.st_dev != target_metadata.st_dev
                or materialized_metadata.st_ino != target_metadata.st_ino
                or materialized_contents != contents
            ):
                raise OwnerEnvError(
                    "Candidate LibreChat materialization binding changed"
                )
        except Exception:
            # Retire through the same move-only primitive as activation. This
            # keeps the exact failure artifact recoverable without deleting a
            # pathname after its validation descriptor has closed.
            try:
                import dev_runtime_activation
            except ImportError:
                pass
            else:
                record = {"repoRoot": str(target.parents[2])}
                try:
                    dev_runtime_activation.retire_owner_env_artifact(
                        directory_descriptor,
                        materialized_name,
                        directory_descriptor,
                        dev_runtime_activation.candidate_env_retirement_name(
                            record,
                            "materializationRetirementName",
                            "mat",
                        ),
                        dev_runtime_activation.candidate_env_retirement_name(
                            record,
                            "retirementTombstoneName",
                            "zero",
                        ),
                        allow_missing=True,
                    )
                except (
                    dev_runtime_activation.ActivationError,
                    OSError,
                ):
                    pass
            raise
    finally:
        os.close(directory_descriptor)


def inspect_source(source: Path) -> dict[str, object]:
    contents, _ = _owned_regular_snapshot(source)
    return upgrade_transaction.librechat_env_semantic_manifest_from_bytes(contents)


def stage(
    source: Path,
    runtime_dir: Path,
    destination: Path,
    manifest: Path,
    target_repo: Path,
    target_commit: str,
) -> dict[str, object]:
    contents, source_binding = _owned_regular_snapshot(source)
    semantic = upgrade_transaction.librechat_env_semantic_manifest_from_bytes(contents)
    target_repo, target_env = _validate_repo_env(
        target_repo,
        target_repo / "viventium_v0_4" / "LibreChat" / ".env",
    )
    target_commit = _validate_commit(target_commit)
    if _current_nested_commit(target_repo) != target_commit:
        raise OwnerEnvError("Candidate LibreChat revision changed before owner snapshot")
    destination = _validate_destination(runtime_dir, destination)
    expected_manifest = destination.with_name("librechat.owner.manifest.json")
    manifest = _lexical(manifest)
    if manifest != expected_manifest:
        raise OwnerEnvError(
            "LibreChat owner environment manifest is outside the candidate runtime"
        )
    if manifest.exists() or manifest.is_symlink():
        metadata = manifest.lstat()
        if (
            manifest.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
        ):
            raise OwnerEnvError("Candidate LibreChat owner manifest is unsafe")
    payload = {
        "schema_version": 2,
        "kind": MANIFEST_KIND,
        "semantic_manifest": semantic,
        "source_binding": {
            **source_binding,
            "file_sha256": semantic["file_sha256"],
        },
        "target_binding": {
            "repo_sha256": _repo_digest(target_repo),
            "git_commit": target_commit,
        },
        "target_precondition": _target_precondition(target_env),
        "materialization_target_name": (
            ".env.viventium-materialized-"
            + hashlib.sha256(
                (
                    semantic["file_sha256"]
                    + ":"
                    + target_commit
                    + ":"
                    + _repo_digest(target_repo)
                ).encode("utf-8")
            ).hexdigest()[:24]
        ),
    }
    _atomic_write(destination, contents)
    _atomic_write(
        manifest,
        (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return {
        "staged": True,
        "exact_file_sha256": semantic["file_sha256"],
        "protected_field_count": sum(
            1
            for item in semantic["protected_fields"].values()
            if item.get("present")
        ),
        "owner_secret_field_count": sum(
            1
            for item in semantic["owner_secret_fields"].values()
            if item.get("present")
        ),
        "unmanaged_field_count": len(semantic["unmanaged_fields"]),
    }


def verify_source(manifest: Path, source: Path) -> dict[str, object]:
    payload = _load_manifest(manifest)
    contents, _ = _owned_regular_snapshot(source)
    digest = hashlib.sha256(contents).hexdigest()
    if digest != payload["source_binding"].get("file_sha256"):
        raise OwnerEnvError("LibreChat owner source changed after it was snapshotted")
    return {"verified": True, "exact_file_match": True}


def verify_compatible(manifest: Path, target: Path) -> dict[str, object]:
    payload = _load_manifest(manifest)
    _verify_target_precondition(payload, target)
    if not target.exists() and not target.is_symlink():
        return {"verified": True, "target_absent": True}
    after = upgrade_transaction.librechat_env_semantic_manifest(target)
    before = payload["semantic_manifest"]
    for field in ("protected_fields", "owner_secret_fields", "unmanaged_fields"):
        if before.get(field) != after.get(field):
            raise OwnerEnvError(
                "Candidate LibreChat environment conflicts with established owner state"
            )
    return {"verified": True, "target_absent": False}


def materialize(
    manifest: Path,
    snapshot: Path,
    target_repo: Path,
    target_env: Path,
    target_commit: str,
) -> dict[str, object]:
    payload = _load_manifest(manifest)
    target_repo, target_env = _validate_repo_env(target_repo, target_env)
    _validate_target_binding(payload, target_repo, target_commit)
    contents, semantic = _snapshot_proof(payload, snapshot)
    _materialize_with_precondition(payload, target_env, contents)
    return {
        "materialized": True,
        "exact_file_sha256": semantic["file_sha256"],
    }


def verify_binding(
    manifest: Path,
    target_repo: Path,
    target_commit: str,
) -> dict[str, object]:
    payload = _load_manifest(manifest)
    target_repo, _ = _validate_repo_env(
        target_repo,
        target_repo / "viventium_v0_4" / "LibreChat" / ".env",
    )
    _validate_target_binding(payload, target_repo, target_commit)
    return {"verified": True, "target_revision_match": True}


def verify(
    manifest: Path,
    target: Path,
    *,
    target_repo: Path | None = None,
    target_commit: str | None = None,
) -> dict[str, object]:
    payload = _load_manifest(manifest)
    if (target_repo is None) != (target_commit is None):
        raise OwnerEnvError(
            "LibreChat target revision verification arguments are incomplete"
        )
    if target_repo is not None and target_commit is not None:
        target_repo, _ = _validate_repo_env(
            target_repo,
            target_repo / "viventium_v0_4" / "LibreChat" / ".env",
        )
        _validate_target_binding(payload, target_repo, target_commit)
    after = upgrade_transaction.librechat_env_semantic_manifest(target)
    proof = upgrade_transaction.compare_librechat_env_semantic_manifests(
        payload["semantic_manifest"],
        after,
    )
    return {
        "verified": proof["verified"],
        "exact_file_match": proof["exact_file_match"],
        "protected_fields_preserved": proof["protected_fields_preserved"],
        "owner_secret_fields_preserved": proof["owner_secret_fields_preserved"],
        "unmanaged_fields_preserved": proof["unmanaged_fields_preserved"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--source", type=Path, required=True)

    stage_parser = subparsers.add_parser("stage")
    stage_parser.add_argument("--source", type=Path, required=True)
    stage_parser.add_argument("--runtime-dir", type=Path, required=True)
    stage_parser.add_argument("--destination", type=Path, required=True)
    stage_parser.add_argument("--manifest", type=Path, required=True)
    stage_parser.add_argument("--target-repo", type=Path, required=True)
    stage_parser.add_argument("--target-commit", required=True)

    source_parser = subparsers.add_parser("verify-source")
    source_parser.add_argument("--manifest", type=Path, required=True)
    source_parser.add_argument("--source", type=Path, required=True)

    compatible_parser = subparsers.add_parser("verify-compatible")
    compatible_parser.add_argument("--manifest", type=Path, required=True)
    compatible_parser.add_argument("--target", type=Path, required=True)

    materialize_parser = subparsers.add_parser("materialize")
    materialize_parser.add_argument("--manifest", type=Path, required=True)
    materialize_parser.add_argument("--snapshot", type=Path, required=True)
    materialize_parser.add_argument("--target-repo", type=Path, required=True)
    materialize_parser.add_argument("--target-env", type=Path, required=True)
    materialize_parser.add_argument("--target-commit", required=True)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--manifest", type=Path, required=True)
    verify_parser.add_argument("--target", type=Path, required=True)
    verify_parser.add_argument("--target-repo", type=Path)
    verify_parser.add_argument("--target-commit")

    binding_parser = subparsers.add_parser("verify-binding")
    binding_parser.add_argument("--manifest", type=Path, required=True)
    binding_parser.add_argument("--target-repo", type=Path, required=True)
    binding_parser.add_argument("--target-commit", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "inspect":
            result = inspect_source(args.source)
        elif args.command == "stage":
            result = stage(
                args.source,
                args.runtime_dir,
                args.destination,
                args.manifest,
                args.target_repo,
                args.target_commit,
            )
        elif args.command == "verify-source":
            result = verify_source(args.manifest, args.source)
        elif args.command == "verify-compatible":
            result = verify_compatible(args.manifest, args.target)
        elif args.command == "materialize":
            result = materialize(
                args.manifest,
                args.snapshot,
                args.target_repo,
                args.target_env,
                args.target_commit,
            )
        elif args.command == "verify-binding":
            result = verify_binding(
                args.manifest,
                args.target_repo,
                args.target_commit,
            )
        else:
            result = verify(
                args.manifest,
                args.target,
                target_repo=args.target_repo,
                target_commit=args.target_commit,
            )
    except (OwnerEnvError, upgrade_transaction.UpgradeTransactionError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
