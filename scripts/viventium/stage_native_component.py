#!/usr/bin/env python3
"""Stage the minimal, deterministic Native runtime surface for bundled components."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path


class StagingError(RuntimeError):
    pass


MACOS_SYSTEM_ALIASES = {
    "tmp": Path("/private/tmp"),
    "var": Path("/private/var"),
}


def lexical_output(path: Path) -> Path:
    value = Path(os.path.abspath(os.fspath(path.expanduser())))
    if sys.platform == "darwin" and len(value.parts) > 1:
        alias_name = value.parts[1]
        expected = MACOS_SYSTEM_ALIASES.get(alias_name)
        alias = Path(value.anchor) / alias_name
        if expected is not None and alias.is_symlink():
            try:
                resolved = alias.resolve(strict=True)
            except OSError as error:
                raise StagingError("macOS system path alias is unavailable") from error
            if resolved != expected or not resolved.is_dir():
                raise StagingError("macOS system path alias is unsafe")
            value = resolved.joinpath(*value.parts[2:])
    return value


PYTHON_EXCLUDED_DIRECTORIES = {
    "__pycache__",
    "ensurepip",
    "idlelib",
    "lib2to3",
    "site-packages",
    "test",
    "tests",
    "tkinter",
    "turtledemo",
    "venv",
}
PYTHON_STANDALONE_LICENSE_FILES = (
    "LICENSE.bdb.txt",
    "LICENSE.bzip2.txt",
    "LICENSE.cpython.txt",
    "LICENSE.expat.txt",
    "LICENSE.libX11.txt",
    "LICENSE.libXau.txt",
    "LICENSE.libedit.txt",
    "LICENSE.libffi.txt",
    "LICENSE.liblzma.txt",
    "LICENSE.libuuid.txt",
    "LICENSE.libxcb.txt",
    "LICENSE.mpdecimal.txt",
    "LICENSE.ncurses.txt",
    "LICENSE.openssl-1.1.txt",
    "LICENSE.openssl-3.txt",
    "LICENSE.sqlite.txt",
    "LICENSE.tcl.txt",
    "LICENSE.tix.txt",
    "LICENSE.zlib.txt",
    "python-licenses.rst",
)


def excluded_python_path(path: Path) -> bool:
    return (
        path.name in PYTHON_EXCLUDED_DIRECTORIES
        or path.name.startswith("config-")
        or path.name.endswith((".pyc", ".pyo"))
        or path.name == "_tkinter.so"
        or (path.name.startswith("_tkinter.") and path.name.endswith(".so"))
    )


def real_source_directory(path: Path) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise StagingError("component source must be a real directory")
    return path.resolve()


def normalized_copy(
    source: Path,
    destination: Path,
    *,
    boundary: Path,
    source_date_epoch: int,
    python_filter: bool = False,
    active: tuple[Path, ...] = (),
) -> None:
    if python_filter and excluded_python_path(source):
        return
    try:
        metadata = source.lstat()
    except OSError as error:
        raise StagingError(f"required component input is unavailable: {source.name}") from error
    if stat.S_ISLNK(metadata.st_mode):
        try:
            target = source.resolve(strict=True)
            target.relative_to(boundary)
        except (OSError, ValueError) as error:
            raise StagingError("component contains an escaping or broken symlink") from error
        if target in active:
            raise StagingError("component contains a symlink cycle")
        normalized_copy(
            target,
            destination,
            boundary=boundary,
            source_date_epoch=source_date_epoch,
            python_filter=python_filter,
            active=(*active, target),
        )
        return
    if stat.S_ISDIR(metadata.st_mode):
        destination.mkdir(parents=True, exist_ok=True)
        destination.chmod(0o755)
        for child in sorted(source.iterdir(), key=lambda item: item.name):
            normalized_copy(
                child,
                destination / child.name,
                boundary=boundary,
                source_date_epoch=source_date_epoch,
                python_filter=python_filter,
                active=active,
            )
        os.utime(destination, (source_date_epoch, source_date_epoch), follow_symlinks=False)
        return
    if not stat.S_ISREG(metadata.st_mode):
        raise StagingError("component contains a non-regular file")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination, follow_symlinks=False)
    destination.chmod(0o755 if metadata.st_mode & 0o111 else 0o644)
    os.utime(destination, (source_date_epoch, source_date_epoch), follow_symlinks=False)


def required_path(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.exists() and not path.is_symlink():
        raise StagingError(f"required component input is unavailable: {relative}")
    return path


def stage_node(source: Path, output: Path, epoch: int) -> None:
    for relative in ("bin/node", "LICENSE"):
        normalized_copy(
            required_path(source, relative),
            output / relative,
            boundary=source,
            source_date_epoch=epoch,
        )


def stage_python(source: Path, output: Path, epoch: int) -> None:
    interpreter = required_path(source, "bin/python3")
    normalized_copy(
        interpreter,
        output / "bin/python3",
        boundary=source,
        source_date_epoch=epoch,
    )
    standard_library_roots = sorted(
        path
        for path in (source / "lib").glob("python[0-9]*.[0-9]*")
        if path.is_dir() and not path.is_symlink()
    )
    if len(standard_library_roots) != 1:
        raise StagingError("Python component must contain exactly one standard library")
    standard_library = standard_library_roots[0]
    normalized_copy(
        standard_library,
        output / "lib" / standard_library.name,
        boundary=source,
        source_date_epoch=epoch,
        python_filter=True,
    )
    license_source = required_path(source, "python-build-standalone-licenses")
    for name in PYTHON_STANDALONE_LICENSE_FILES:
        normalized_copy(
            required_path(license_source, name),
            output / "share" / "licenses" / "python-build-standalone" / name,
            boundary=source,
            source_date_epoch=epoch,
        )


def stage_mongodb(source: Path, output: Path, epoch: int) -> None:
    for relative in (
        "bin/mongod",
        "LICENSE-Community.txt",
        "MPL-2",
        "THIRD-PARTY-NOTICES",
    ):
        normalized_copy(
            required_path(source, relative),
            output / relative,
            boundary=source,
            source_date_epoch=epoch,
        )


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        metadata = path.lstat()
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise StagingError("staged component contains an unsupported filesystem entry")
        digest.update(("d" if path.is_dir() else "f").encode("ascii"))
        digest.update(b"\0")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(f"{stat.S_IMODE(metadata.st_mode):04o}".encode("ascii"))
        digest.update(b"\0")
        if path.is_file():
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
    return digest.hexdigest()


def stage_component(
    component: str,
    source_root: Path,
    output_root: Path,
    *,
    source_date_epoch: int,
) -> dict[str, object]:
    if component not in {"node", "python", "mongodb"}:
        raise StagingError("unsupported Native component")
    if source_date_epoch < 315532800:
        raise StagingError("source date epoch is outside the supported range")
    source = real_source_directory(source_root)
    output = lexical_output(output_root)
    if output.exists() or output.is_symlink():
        raise StagingError("component output already exists")
    if output == source or source in output.parents:
        raise StagingError("component output must stay outside the source tree")
    current = Path(output.anchor)
    for part in output.parent.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise StagingError("component output ancestor is a symlink")
        if current.exists():
            if not current.is_dir():
                raise StagingError("component output ancestor is not a directory")
            continue
        current.mkdir(mode=0o755)
        if current.is_symlink() or not current.is_dir():
            raise StagingError("component output ancestor is unsafe")
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent))
    try:
        {
            "node": stage_node,
            "python": stage_python,
            "mongodb": stage_mongodb,
        }[component](source, temporary, source_date_epoch)
        for directory in sorted(
            (path for path in temporary.rglob("*") if path.is_dir()), reverse=True
        ):
            directory.chmod(0o755)
            os.utime(directory, (source_date_epoch, source_date_epoch), follow_symlinks=False)
        temporary.chmod(0o755)
        os.utime(temporary, (source_date_epoch, source_date_epoch), follow_symlinks=False)
        if any(path.is_symlink() for path in temporary.rglob("*")):
            raise StagingError("staged component contains a symlink")
        digest = tree_digest(temporary)
        file_count = sum(1 for path in temporary.rglob("*") if path.is_file())
        byte_count = sum(path.stat().st_size for path in temporary.rglob("*") if path.is_file())
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {
        "bytes": byte_count,
        "component": component,
        "files": file_count,
        "sha256": digest,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--component", choices=("node", "python", "mongodb"), required=True)
    value.add_argument("--source-root", type=Path, required=True)
    value.add_argument("--output-root", type=Path, required=True)
    value.add_argument("--source-date-epoch", type=int, required=True)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = stage_component(
            args.component,
            args.source_root,
            args.output_root,
            source_date_epoch=args.source_date_epoch,
        )
    except (OSError, StagingError, ValueError) as error:
        print(f"Native component staging failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
