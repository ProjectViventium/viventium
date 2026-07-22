#!/usr/bin/env python3
"""Pack and unpack an exact Native candidate without artifact-service mode loss."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


MAX_MEMBERS = 300_000
MAX_MEMBER_BYTES = 4 * 1024 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024 * 1024
SAFE_FILE_MODES = {0o644, 0o755}
SHA256_RE = re.compile(r"[0-9a-f]{64}")
MACOS_SYSTEM_ALIASES = {
    "tmp": Path("/private/tmp"),
    "var": Path("/private/var"),
}


class TransportError(RuntimeError):
    pass


def lexical(path: Path) -> Path:
    path = Path(os.path.abspath(os.fspath(path.expanduser())))
    if os.uname().sysname == "Darwin" and len(path.parts) > 1:
        alias_name = path.parts[1]
        expected = MACOS_SYSTEM_ALIASES.get(alias_name)
        alias = Path(path.anchor) / alias_name
        if expected is not None and alias.is_symlink():
            try:
                resolved_alias = alias.resolve(strict=True)
            except OSError as error:
                raise TransportError("macOS system path alias is unavailable") from error
            if resolved_alias != expected or not resolved_alias.is_dir():
                raise TransportError("macOS system path alias is unsafe")
            path = resolved_alias.joinpath(*path.parts[2:])
    return path


def ensure_directory_chain(path: Path, *, create: bool, label: str) -> Path:
    path = lexical(path)
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise TransportError(f"{label} ancestor component is a symlink")
        if current.exists():
            if not current.is_dir():
                raise TransportError(f"{label} ancestor component is not a directory")
            continue
        if not create:
            raise TransportError(f"{label} ancestor directory is unavailable")
        current.mkdir(mode=0o755)
        if current.is_symlink() or not current.is_dir():
            raise TransportError(f"{label} ancestor directory is unsafe")
    return path


def require_new_output(path: Path, label: str) -> Path:
    path = lexical(path)
    if path.exists() or path.is_symlink():
        raise TransportError(f"{label} already exists")
    ensure_directory_chain(path.parent, create=True, label=label)
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def candidate_paths(candidate_root: Path) -> list[Path]:
    if candidate_root.is_symlink() or not candidate_root.is_dir():
        raise TransportError("candidate root must be a regular directory")
    return [candidate_root, *sorted(candidate_root.rglob("*"), key=lambda item: item.as_posix())]


def validate_source(candidate_root: Path) -> None:
    for path in candidate_paths(candidate_root):
        metadata = path.lstat()
        relative = path.relative_to(candidate_root).as_posix() or "."
        if stat.S_ISLNK(metadata.st_mode):
            raise TransportError(f"candidate contains a symlink: {relative}")
        if stat.S_ISDIR(metadata.st_mode):
            if stat.S_IMODE(metadata.st_mode) != 0o755:
                raise TransportError(f"candidate directory mode is unsafe: {relative}")
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise TransportError(f"candidate contains a non-regular file: {relative}")
        if metadata.st_nlink != 1:
            raise TransportError(f"candidate contains a hard link: {relative}")
        if stat.S_IMODE(metadata.st_mode) not in SAFE_FILE_MODES:
            raise TransportError(f"candidate file mode is unsafe: {relative}")


def normalize_tarinfo(info: tarfile.TarInfo) -> tarfile.TarInfo:
    if not (info.isdir() or info.isreg()):
        raise TransportError(f"candidate contains a non-regular archive member: {info.name}")
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.pax_headers = {}
    info.mtime = 0
    info.mode = 0o755 if info.isdir() else stat.S_IMODE(info.mode)
    return info


def pack(candidate_root: Path, archive: Path, digest_output: Path) -> Path:
    candidate_root = lexical(candidate_root)
    if candidate_root.is_symlink():
        raise TransportError("candidate root must not be a symlink")
    if not candidate_root.is_dir():
        raise TransportError("candidate root must be a regular directory")
    ensure_directory_chain(candidate_root, create=False, label="candidate root")
    candidate_root = candidate_root.resolve(strict=True)
    archive = lexical(archive)
    digest_output = lexical(digest_output)
    if archive == digest_output:
        raise TransportError("archive and digest outputs must be different")
    if candidate_root == archive or candidate_root in archive.parents:
        raise TransportError("transport output must stay outside the candidate root")
    if candidate_root == digest_output or candidate_root in digest_output.parents:
        raise TransportError("digest output must stay outside the candidate root")
    archive = require_new_output(archive, "archive output")
    digest_output = require_new_output(digest_output, "digest output")
    validate_source(candidate_root)
    with tempfile.NamedTemporaryFile(dir=archive.parent, prefix=".candidate-", suffix=".tar", delete=False) as handle:
        temporary_archive = Path(handle.name)
    try:
        with tarfile.open(temporary_archive, "w", format=tarfile.PAX_FORMAT) as tar:
            tar.add(candidate_root, arcname="candidate", recursive=False, filter=normalize_tarinfo)
            for path in candidate_paths(candidate_root)[1:]:
                archive_name = PurePosixPath("candidate") / path.relative_to(candidate_root).as_posix()
                tar.add(path, arcname=archive_name.as_posix(), recursive=False, filter=normalize_tarinfo)
        os.replace(temporary_archive, archive)
    finally:
        temporary_archive.unlink(missing_ok=True)
    digest = sha256_file(archive)
    with tempfile.NamedTemporaryFile(
        dir=digest_output.parent,
        prefix=".candidate-digest-",
        mode="w",
        encoding="utf-8",
        delete=False,
    ) as handle:
        handle.write(f"{digest}\n")
        temporary_digest = Path(handle.name)
    try:
        temporary_digest.chmod(0o644)
        os.replace(temporary_digest, digest_output)
    finally:
        temporary_digest.unlink(missing_ok=True)
    return archive


def expected_digest(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8")
    except OSError as error:
        raise TransportError("candidate transport digest is unavailable") from error
    if not value.endswith("\n") or not SHA256_RE.fullmatch(value.rstrip("\n")):
        raise TransportError("candidate transport digest is invalid")
    return value.rstrip("\n")


def validate_member(member: tarfile.TarInfo, seen: set[str], folded: dict[str, str]) -> None:
    pure = PurePosixPath(member.name)
    parts = pure.parts
    if pure.is_absolute() or not parts or parts[0] != "candidate" or any(part in {"", ".", ".."} for part in parts):
        raise TransportError(f"unsafe member path: {member.name}")
    canonical = pure.as_posix()
    if canonical in seen:
        raise TransportError(f"duplicate archive member: {canonical}")
    case_key = canonical.casefold()
    if case_key in folded and folded[case_key] != canonical:
        raise TransportError(f"case-colliding archive member: {canonical}")
    seen.add(canonical)
    folded[case_key] = canonical
    if not (member.isdir() or member.isreg()):
        raise TransportError(f"archive contains a non-regular member: {canonical}")
    expected_mode = 0o755 if member.isdir() else stat.S_IMODE(member.mode)
    if expected_mode not in SAFE_FILE_MODES or (member.isdir() and expected_mode != 0o755):
        raise TransportError(f"archive member mode is unsafe: {canonical}")
    if member.size < 0 or member.size > MAX_MEMBER_BYTES:
        raise TransportError(f"archive member size is unsafe: {canonical}")
    if member.uid != 0 or member.gid != 0 or member.uname or member.gname:
        raise TransportError(f"archive member ownership metadata is unsafe: {canonical}")


def unpack(archive: Path, digest_path: Path, output_root: Path) -> Path:
    archive = lexical(archive)
    digest_path = lexical(digest_path)
    ensure_directory_chain(archive.parent, create=False, label="archive input")
    ensure_directory_chain(digest_path.parent, create=False, label="digest input")
    if archive.is_symlink() or not archive.is_file():
        raise TransportError("candidate transport archive must be a regular file")
    if digest_path.is_symlink() or not digest_path.is_file():
        raise TransportError("candidate transport digest must be a regular file")
    if sha256_file(archive) != expected_digest(digest_path):
        raise TransportError("candidate transport digest mismatch")
    output_root = lexical(output_root)
    if output_root.is_symlink():
        raise TransportError("candidate extraction directory must not be a symlink")
    if output_root.exists():
        raise TransportError("candidate extraction directory already exists")
    ensure_directory_chain(output_root.parent, create=True, label="candidate extraction")
    output_root.mkdir(mode=0o755)
    seen: set[str] = set()
    folded: dict[str, str] = {}
    total_size = 0
    with tarfile.open(archive, "r") as tar:
        members = tar.getmembers()
        if not members or len(members) > MAX_MEMBERS:
            raise TransportError("candidate archive member count is unsafe")
        for member in members:
            validate_member(member, seen, folded)
            total_size += member.size
            if total_size > MAX_TOTAL_BYTES:
                raise TransportError("candidate archive expands beyond the safety limit")
        if "candidate" not in seen:
            raise TransportError("candidate archive root is missing")
        tar.extractall(path=output_root, members=members, filter="data")
    extracted = output_root / "candidate"
    validate_source(extracted)
    return extracted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pack_parser = commands.add_parser("pack")
    pack_parser.add_argument("--candidate-root", type=Path, required=True)
    pack_parser.add_argument("--archive", type=Path, required=True)
    pack_parser.add_argument("--digest-output", type=Path, required=True)
    unpack_parser = commands.add_parser("unpack")
    unpack_parser.add_argument("--archive", type=Path, required=True)
    unpack_parser.add_argument("--digest", type=Path, required=True)
    unpack_parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "pack":
            archive = pack(args.candidate_root, args.archive, args.digest_output)
            result = {"result": "PASS", "mode": "pack", "sha256": sha256_file(archive)}
        else:
            unpack(args.archive, args.digest, args.output_root)
            result = {"result": "PASS", "mode": "unpack"}
    except (OSError, tarfile.TarError, TransportError) as error:
        parser.exit(1, f"Native candidate transport failed: {error}\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
