#!/usr/bin/env python3
"""Verify every shipped macOS code object can run at the declared Native minimum."""

from __future__ import annotations

import argparse
import json
import plistlib
import re
import subprocess
from pathlib import Path, PurePosixPath


VERSION_RE = re.compile(r"[0-9]+(?:\.[0-9]+){1,2}")
MACHO_MAGICS = {
    b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xce",
    b"\xcf\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
    b"\xca\xfe\xba\xbe",
    b"\xbe\xba\xfe\xca",
    b"\xca\xfe\xba\xbf",
    b"\xbf\xba\xfe\xca",
}


class CompatibilityError(RuntimeError):
    pass


def version_tuple(value: str) -> tuple[int, int, int]:
    if not VERSION_RE.fullmatch(value):
        raise CompatibilityError(f"invalid macOS version: {value}")
    parts = [int(part) for part in value.split(".")]
    return tuple((parts + [0, 0])[:3])


def read_minimum(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8")
    except OSError as error:
        raise CompatibilityError("Native minimum-macOS policy is unavailable") from error
    if not value.endswith("\n") or not VERSION_RE.fullmatch(value.rstrip("\n")):
        raise CompatibilityError("Native minimum-macOS policy is invalid")
    return value.rstrip("\n")


def safe_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise CompatibilityError("Native code inventory contains an unsafe path")
    return path


def bundle_executable(app: Path, declared_minimum: str) -> Path:
    info_path = app / "Contents" / "Info.plist"
    try:
        info = plistlib.loads(info_path.read_bytes())
    except (OSError, plistlib.InvalidFileException) as error:
        raise CompatibilityError(f"Native app metadata is invalid: {app.name}") from error
    executable_name = info.get("CFBundleExecutable")
    if not isinstance(executable_name, str) or not executable_name or "/" in executable_name:
        raise CompatibilityError(f"Native app executable metadata is invalid: {app.name}")
    app_minimum = info.get("LSMinimumSystemVersion")
    if not isinstance(app_minimum, str) or version_tuple(app_minimum) > version_tuple(declared_minimum):
        raise CompatibilityError(f"Native app cannot launch at declared minimum {declared_minimum}: {app.name}")
    executable = app / "Contents" / "MacOS" / executable_name
    if executable.is_symlink() or not executable.is_file():
        raise CompatibilityError(f"Native app executable is unavailable: {app.name}")
    return executable


def is_macho(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(4) in MACHO_MAGICS
    except OSError as error:
        raise CompatibilityError(f"could not read Native code candidate: {path.name}") from error


def bundle_code_objects(app: Path, declared_minimum: str) -> list[Path]:
    main_executable = bundle_executable(app, declared_minimum)
    result: list[Path] = []
    for path in sorted(app.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise CompatibilityError(f"Native app contains a symlink: {app.name}")
        if path.is_file() and is_macho(path):
            result.append(path)
    if main_executable not in result:
        raise CompatibilityError(f"Native app executable is not Mach-O: {app.name}")
    return result


def deployment_targets(path: Path, otool: Path) -> list[str]:
    completed = subprocess.run(
        [str(otool), "-l", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise CompatibilityError(f"could not inspect Native code object: {path.name}")
    targets: list[str] = []
    awaiting: str | None = None
    build_platform: str | None = None
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if line == "cmd LC_BUILD_VERSION":
            awaiting = "minos"
            build_platform = None
            continue
        if line == "cmd LC_VERSION_MIN_MACOSX":
            awaiting = "version"
            build_platform = "macos"
            continue
        if awaiting == "minos" and line.startswith("platform "):
            build_platform = line.split(None, 1)[1]
            continue
        if awaiting and line.startswith(f"{awaiting} "):
            value = line.split(None, 1)[1]
            if awaiting == "minos" and build_platform not in {"1", "MACOS"}:
                raise CompatibilityError(f"Native code object targets a non-macOS platform: {path.name}")
            version_tuple(value)
            targets.append(value)
            awaiting = None
            build_platform = None
    if not targets:
        raise CompatibilityError(f"Native code object has no macOS deployment target: {path.name}")
    return targets


def code_objects(candidate_root: Path, declared_minimum: str) -> list[Path]:
    payload = candidate_root / "payload"
    inventory = payload / "release-metadata" / "apple-code-paths.txt"
    try:
        entries = inventory.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise CompatibilityError("Native Apple code inventory is unavailable") from error
    if not entries or any(not entry for entry in entries):
        raise CompatibilityError("Native Apple code inventory is invalid")
    result: list[Path] = []
    for entry in entries:
        path = payload.joinpath(*safe_relative(entry).parts)
        if path.is_symlink() or not path.exists():
            raise CompatibilityError("Native Apple code inventory target is unavailable")
        if path.suffix == ".app":
            result.extend(bundle_code_objects(path, declared_minimum))
        elif not path.is_file() or not is_macho(path):
            raise CompatibilityError("Native Apple code inventory target is not Mach-O")
        else:
            result.append(path)
    bootstrap = candidate_root / "bootstrap" / "ViventiumBootstrap.app"
    result.extend(bundle_code_objects(bootstrap, declared_minimum))
    if len({path.resolve() for path in result}) != len(result):
        raise CompatibilityError("Native Apple code inventory contains duplicate code objects")
    result_set = {path.resolve() for path in result}
    discovered: set[Path] = set()
    for path in sorted(candidate_root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise CompatibilityError("Native candidate contains a symlink")
        if path.is_file() and is_macho(path):
            discovered.add(path.resolve())
    if discovered != result_set:
        missing = sorted(path.relative_to(candidate_root).as_posix() for path in discovered - result_set)
        stale = sorted(path.relative_to(candidate_root).as_posix() for path in result_set - discovered)
        detail = (missing or stale)[0] if (missing or stale) else "unknown"
        raise CompatibilityError(f"Native Apple code inventory does not cover every Mach-O object: {detail}")
    return result


def verify(candidate_root: Path, minimum_policy: Path, otool: Path = Path("/usr/bin/otool")) -> dict[str, object]:
    if candidate_root.is_symlink() or not candidate_root.is_dir():
        raise CompatibilityError("Native candidate root is unavailable")
    declared = read_minimum(minimum_policy)
    declared_tuple = version_tuple(declared)
    objects = code_objects(candidate_root, declared)
    maximum = (0, 0, 0)
    maximum_text = "0.0"
    for code_object in objects:
        for target in deployment_targets(code_object, otool):
            parsed = version_tuple(target)
            if parsed > declared_tuple:
                relative = code_object.relative_to(candidate_root).as_posix()
                raise CompatibilityError(
                    f"Native code object requires macOS {target}, above declared {declared}: {relative}"
                )
            if parsed > maximum:
                maximum = parsed
                maximum_text = target
    return {
        "result": "PASS",
        "declared_minimum": declared,
        "maximum_binary_requirement": maximum_text,
        "checked_code_objects": len(objects),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--minimum-macos-file", type=Path, required=True)
    parser.add_argument("--otool", type=Path, default=Path("/usr/bin/otool"))
    args = parser.parse_args()
    try:
        result = verify(args.candidate_root, args.minimum_macos_file, args.otool)
    except (OSError, CompatibilityError) as error:
        parser.exit(1, f"Native macOS compatibility verification failed: {error}\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
