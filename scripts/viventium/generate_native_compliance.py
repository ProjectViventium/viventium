#!/usr/bin/env python3
"""Generate deterministic SBOM, notices, and license inventory for one exact payload tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path, PurePosixPath

from stage_native_component import PYTHON_STANDALONE_LICENSE_FILES


class ComplianceError(RuntimeError):
    pass


NOTICE_NAMES = (
    "LICENSE",
    "LICENSE.md",
    "LICENSE.txt",
    "LICENCE",
    "LICENCE.md",
    "COPYING",
    "NOTICE",
)
NOTICE_NAME_PATTERN = re.compile(r"^(?:LICENSE|LICENCE|COPYING|NOTICE)(?:[._-].*)?$", re.IGNORECASE)
ALLOWED_LICENSE_TOKENS = {
    "0BSD", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "BlueOak-1.0.0",
    "CC0-1.0", "ISC", "MIT", "MPL-2.0", "OpenSSL", "Python-2.0", "Sleepycat",
    "SSPL-1.0", "TCL", "Unlicense", "X11", "Zlib", "blessing", "bzip2-1.0.6",
}
PYTHON_STANDALONE_LICENSE_EXPRESSION = (
    "Sleepycat AND bzip2-1.0.6 AND Python-2.0 AND MIT AND BSD-3-Clause AND 0BSD "
    "AND BSD-2-Clause AND X11 AND OpenSSL AND Apache-2.0 AND blessing AND TCL AND Zlib"
)


def package_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ComplianceError(f"invalid package metadata: {path.name}") from error
    if not isinstance(value, dict) or not isinstance(value.get("name"), str):
        raise ComplianceError(f"invalid package metadata: {path.name}")
    return value


def json_object(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ComplianceError(f"{label} is unavailable or invalid") from error
    if not isinstance(value, dict):
        raise ComplianceError(f"{label} is unavailable or invalid")
    return value


def safe_owned_file(root: Path, relative: object, label: str) -> Path:
    if not isinstance(relative, str):
        raise ComplianceError(f"{label} contains an invalid path")
    value = PurePosixPath(relative)
    if value.is_absolute() or not value.parts or ".." in value.parts or "\\" in relative:
        raise ComplianceError(f"{label} contains an unsafe path")
    path = root.joinpath(*value.parts)
    if path.is_symlink() or not path.is_file():
        raise ComplianceError(f"{label} file is missing: {relative}")
    try:
        path.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as error:
        raise ComplianceError(f"{label} file escapes its root") from error
    return path


def browser_lock_path(relative: object) -> str:
    if not isinstance(relative, str):
        raise ComplianceError("browser closure contains an invalid package-lock path")
    value = PurePosixPath(relative)
    if (
        value.is_absolute()
        or not value.parts
        or "node_modules" not in value.parts
        or value.parts[-1] == "node_modules"
        or ".." in value.parts
        or "\\" in relative
    ):
        raise ComplianceError("browser closure contains an unsafe package-lock path")
    return relative


def exact_file_record(root: Path, record: object, label: str) -> Path:
    if not isinstance(record, dict):
        raise ComplianceError(f"browser compliance contains an invalid {label} record")
    expected = record.get("sha256")
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ComplianceError(f"browser compliance contains an invalid {label} digest")
    path = safe_owned_file(root, record.get("path"), f"browser compliance {label}")
    if sha256_file(path) != expected:
        raise ComplianceError(f"browser compliance {label} hash mismatch")
    return path


def locked_identity_matches(
    record: object,
    lock_path: str,
    lock_entry: object,
    *,
    expected_name: str | None = None,
) -> bool:
    return (
        isinstance(record, dict)
        and isinstance(lock_entry, dict)
        and record.get("lockPath") == lock_path
        and (expected_name is None or record.get("name") == expected_name)
        and isinstance(record.get("version"), str)
        and bool(record.get("version"))
        and isinstance(record.get("resolved"), str)
        and bool(record.get("resolved"))
        and isinstance(record.get("integrity"), str)
        and bool(record.get("integrity"))
        and record["version"] == lock_entry.get("version")
        and record["resolved"] == lock_entry.get("resolved")
        and record["integrity"] == lock_entry.get("integrity")
    )


def browser_inventory(payload: Path) -> list[dict[str, object]]:
    librechat = payload / "runtime" / "librechat"
    compliance = librechat / "client" / "dist-compliance"
    closure = json_object(compliance / "module-closure.json", "browser module closure")
    manifest = json_object(compliance / "manifest.json", "browser compliance manifest")
    package_lock = json_object(librechat / "package-lock.json", "LibreChat package lock")
    overrides = json_object(
        librechat / "client" / "third_party" / "browser-compliance" / "overrides.json",
        "browser compliance overrides",
    )
    closure_paths = closure.get("packageLockPaths")
    manifest_packages = manifest.get("packages")
    lock_packages = package_lock.get("packages")
    if (
        closure.get("schemaVersion") != 1
        or manifest.get("schemaVersion") != 1
        or package_lock.get("lockfileVersion") not in (2, 3)
        or overrides.get("schemaVersion") != 1
        or not isinstance(closure_paths, list)
        or not isinstance(manifest_packages, list)
        or not isinstance(lock_packages, dict)
        or not isinstance(overrides.get("sources"), list)
        or not isinstance(overrides.get("packageOverrides"), list)
        or not isinstance(overrides.get("supplementalNotices"), list)
    ):
        raise ComplianceError("browser compliance schema is unsupported")
    normalized_paths = [browser_lock_path(value) for value in closure_paths]
    if len(normalized_paths) != len(set(normalized_paths)):
        raise ComplianceError("browser closure duplicates a package-lock path")
    if normalized_paths != [
        item.get("lockPath") if isinstance(item, dict) else None for item in manifest_packages
    ]:
        raise ComplianceError("browser closure and compliance package sets disagree")

    source_root = librechat / "client" / "third_party" / "browser-compliance"
    sources: dict[str, dict[str, object]] = {}
    for source in overrides["sources"]:
        if (
            not isinstance(source, dict)
            or not isinstance(source.get("id"), str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", str(source["id"]))
            or source.get("provenance") != "exact-package-revision"
            or not isinstance(source.get("repository"), str)
            or not str(source["repository"]).startswith("https://github.com/")
            or not isinstance(source.get("revision"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", str(source["revision"]))
            or not isinstance(source.get("sourcePath"), str)
            or not source.get("sourcePath")
            or source.get("contentRole") not in {"license", "license-text-in-readme", "notice"}
            or not isinstance(source.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", str(source["sha256"]))
            or source["id"] in sources
        ):
            raise ComplianceError("browser curated legal-source metadata is invalid")
        source_file = safe_owned_file(source_root, source.get("localFile"), "browser curated source")
        if sha256_file(source_file) != source["sha256"]:
            raise ComplianceError("browser curated legal-source hash mismatch")
        sources[str(source["id"])] = source

    package_overrides: dict[str, dict[str, object]] = {}
    for record in overrides["packageOverrides"]:
        lock_path = browser_lock_path(record.get("lockPath") if isinstance(record, dict) else None)
        lock_entry = lock_packages.get(lock_path)
        if (
            lock_path not in normalized_paths
            or lock_path in package_overrides
            or not locked_identity_matches(record, lock_path, lock_entry)
            or not isinstance(record.get("license"), str)
            or record.get("legalSourceId") not in sources
            or sources[str(record["legalSourceId"])]["contentRole"] == "notice"
        ):
            raise ComplianceError("browser curated package override is stale or invalid")
        package_overrides[lock_path] = record

    supplemental: dict[str, dict[str, object]] = {}
    for notice in overrides["supplementalNotices"]:
        if not isinstance(notice, dict) or notice.get("sourceId") not in sources:
            raise ComplianceError("browser supplemental notice is invalid")
        source = sources[str(notice["sourceId"])]
        bindings = notice.get("packageBindings")
        if source["contentRole"] != "notice" or not isinstance(bindings, list):
            raise ComplianceError("browser supplemental notice is invalid")
        for binding in bindings:
            lock_path = browser_lock_path(
                binding.get("lockPath") if isinstance(binding, dict) else None
            )
            if (
                lock_path not in normalized_paths
                or lock_path in supplemental
                or not locked_identity_matches(binding, lock_path, lock_packages.get(lock_path))
            ):
                raise ComplianceError("browser supplemental notice binding is stale or invalid")
            supplemental[lock_path] = source

    packages: list[dict[str, object]] = []
    referenced_sources: set[str] = set()
    referenced_files: set[str] = {"module-closure.json", "manifest.json"}
    for lock_path, package_record in zip(normalized_paths, manifest_packages, strict=True):
        lock_entry = lock_packages.get(lock_path)
        package_root = librechat.joinpath(*PurePosixPath(lock_path).parts)
        metadata = exact_file_record(compliance, package_record.get("packageMetadata"), "package metadata")
        installed_metadata = package_json(package_root / "package.json")
        copied_metadata = package_json(metadata)
        if (
            not locked_identity_matches(
                package_record,
                lock_path,
                lock_entry,
                expected_name=str(copied_metadata.get("name")),
            )
            or copied_metadata.get("name") != installed_metadata.get("name")
            or copied_metadata.get("version") != installed_metadata.get("version")
            or sha256_file(metadata) != sha256_file(package_root / "package.json")
            or not isinstance(package_record.get("license"), str)
            or not isinstance(package_record.get("licenseSource"), str)
            or not isinstance(package_record.get("legalFiles"), list)
            or not package_record["legalFiles"]
        ):
            raise ComplianceError("browser compliance package identity is incomplete")
        expected_directory = (
            f"licenses/{lock_path.replace('/', '__')}--"
            f"{hashlib.sha256(lock_path.encode()).hexdigest()[:12]}"
        )
        if package_record["packageMetadata"].get("path") != f"{expected_directory}/package.json":
            raise ComplianceError("browser package-metadata destination is not deterministic")
        license_source = str(package_record["licenseSource"])
        package_override = package_overrides.get(lock_path)
        if package_override and package_override.get("name") != package_record["name"]:
            raise ComplianceError("browser curated package override name is mismatched")
        if lock_path in supplemental and any(
            binding.get("lockPath") == lock_path
            and binding.get("name") != package_record["name"]
            for notice in overrides["supplementalNotices"]
            if isinstance(notice, dict)
            for binding in notice.get("packageBindings", [])
            if isinstance(binding, dict)
        ):
            raise ComplianceError("browser supplemental notice package name is mismatched")
        if license_source == "package-lock.json#license":
            expected_license = lock_entry.get("license") if isinstance(lock_entry, dict) else None
        elif license_source == "installed-package.json#license(s)":
            expected_license = declared_license(
                copied_metadata.get("license", copied_metadata.get("licenses"))
            )
        elif license_source.startswith("curated-source:") and package_override:
            expected_license = package_override["license"]
            if license_source != f"curated-source:{package_override['legalSourceId']}":
                raise ComplianceError("browser curated license source is mismatched")
        else:
            raise ComplianceError("browser license source is unsupported")
        if package_record["license"] != expected_license:
            raise ComplianceError("browser license identity disagrees with its exact source")

        expected_curated = []
        if package_override:
            expected_curated.append(sources[str(package_override["legalSourceId"])])
        if lock_path in supplemental:
            expected_curated.append(supplemental[lock_path])
        notices: list[Path] = []
        seen_curated: set[str] = set()
        for legal_file in package_record["legalFiles"]:
            legal_path = exact_file_record(compliance, legal_file, "legal file")
            relative = legal_path.relative_to(compliance).as_posix()
            if (
                PurePosixPath(relative).parent.as_posix() != expected_directory
                or not NOTICE_NAME_PATTERN.fullmatch(PurePosixPath(relative).name)
            ):
                raise ComplianceError("browser legal-file destination is not deterministic")
            provenance = legal_file.get("provenance") if isinstance(legal_file, dict) else None
            if provenance is not None:
                if not isinstance(provenance, dict) or provenance.get("sourceId") not in sources:
                    raise ComplianceError("browser legal-file provenance is invalid")
                source = sources[str(provenance["sourceId"])]
                expected_provenance = {
                    "sourceId": source["id"],
                    "repository": source["repository"],
                    "revision": source["revision"],
                    "sourcePath": source["sourcePath"],
                    "sourceSha256": source["sha256"],
                    "contentRole": source["contentRole"],
                    "provenance": source["provenance"],
                }
                if provenance != expected_provenance or legal_file.get("sha256") != source["sha256"]:
                    raise ComplianceError("browser legal-file provenance is mismatched")
                seen_curated.add(str(source["id"]))
                referenced_sources.add(str(source["id"]))
            notices.append(legal_path)
            if relative in referenced_files:
                raise ComplianceError("browser compliance duplicates a shipped file")
            referenced_files.add(relative)
        if seen_curated != {str(source["id"]) for source in expected_curated}:
            raise ComplianceError("browser curated legal-file set is incomplete")
        metadata_relative = metadata.relative_to(compliance).as_posix()
        if metadata_relative in referenced_files:
            raise ComplianceError("browser compliance duplicates package metadata")
        referenced_files.add(metadata_relative)
        packages.append({
            "name": package_record["name"],
            "version": package_record["version"],
            "license": package_record["license"],
            "root": compliance / expected_directory,
            "path": f"runtime/librechat/client/dist-compliance/{expected_directory}",
            "notices": notices,
            "inventory_scope": "compiled-browser",
            "lock_path": lock_path,
        })

    vendored = manifest.get("vendoredComponents")
    if not isinstance(vendored, list):
        raise ComplianceError("browser vendored-component inventory is invalid")
    for component in vendored:
        if (
            not isinstance(component, dict)
            or not isinstance(component.get("name"), str)
            or not isinstance(component.get("upstreamPackage"), str)
            or not isinstance(component.get("upstreamVersion"), str)
            or not isinstance(component.get("upstreamIntegrity"), str)
            or not isinstance(component.get("license"), str)
            or component.get("modified") is not True
            or not isinstance(component.get("legalFiles"), list)
            or not component["legalFiles"]
        ):
            raise ComplianceError("browser vendored-component identity is incomplete")
        matching_locks = [
            value for key, value in lock_packages.items()
            if isinstance(value, dict)
            and key.endswith(f"node_modules/{component['upstreamPackage']}")
            and value.get("version") == component["upstreamVersion"]
            and value.get("integrity") == component["upstreamIntegrity"]
        ]
        if len(matching_locks) != 1:
            raise ComplianceError("browser vendored component does not match one locked upstream")
        records = [component.get("notice"), *component["legalFiles"]]
        notices = [exact_file_record(compliance, record, "vendored legal file") for record in records]
        for notice in notices:
            relative = notice.relative_to(compliance).as_posix()
            if (
                PurePosixPath(relative).parts[0] != "vendored"
                or not NOTICE_NAME_PATTERN.fullmatch(PurePosixPath(relative).name)
                or relative in referenced_files
            ):
                raise ComplianceError("browser compliance duplicates a vendored legal file")
            referenced_files.add(relative)
        packages.append({
            "name": component["name"],
            "version": component["upstreamVersion"],
            "license": component["license"],
            "root": notices[0].parent,
            "path": f"runtime/librechat/client/dist-compliance/{notices[0].parent.relative_to(compliance).as_posix()}",
            "notices": notices,
            "inventory_scope": "compiled-browser",
            "lock_path": f"vendored:{component['upstreamPackage']}",
        })

    if referenced_sources != set(sources):
        raise ComplianceError("browser curated legal-source inventory contains stale entries")
    shipped_files = {
        path.relative_to(compliance).as_posix()
        for root_name in ("licenses", "vendored")
        for path in (compliance / root_name).rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if shipped_files != referenced_files - {"module-closure.json", "manifest.json"}:
        raise ComplianceError("browser compliance contains unreferenced or missing shipped files")
    return packages


def locked_package_roots(root: Path) -> list[tuple[str, Path]]:
    lock_path = root / "package-lock.json"
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ComplianceError("LibreChat package-lock inventory is unavailable or invalid") from error
    records = lock.get("packages")
    if lock.get("lockfileVersion") not in (2, 3) or not isinstance(records, dict):
        raise ComplianceError("LibreChat package-lock physical package graph is unsupported")
    values: list[tuple[str, Path]] = []
    for relative, record in sorted(records.items()):
        if relative == "":
            continue
        if not isinstance(relative, str):
            raise ComplianceError("LibreChat package-lock contains an unsafe physical package path")
        value = PurePosixPath(relative)
        if (
            value.is_absolute()
            or ".." in value.parts
            or not isinstance(record, dict)
        ):
            raise ComplianceError("LibreChat package-lock contains an unsafe physical package path")
        package_root = root.joinpath(*value.parts)
        metadata = package_root / "package.json"
        if not metadata.is_file():
            # npm retains lock records for pruned optional/platform packages. They are not shipped.
            continue
        try:
            metadata.resolve(strict=True).relative_to(root.resolve(strict=True))
        except (OSError, ValueError) as error:
            raise ComplianceError("LibreChat physical package graph escapes the payload") from error
        values.append((relative, package_root))
    return values


def declared_license(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict) and isinstance(value.get("type"), str):
        return str(value["type"])
    if isinstance(value, list):
        values = [declared_license(item) for item in value]
        values = [item for item in values if item != "NOASSERTION"]
        if values:
            return " OR ".join(values)
    return "NOASSERTION"


def license_allowed(expression: str) -> bool:
    if expression == "NOASSERTION":
        return False
    tokens = re.findall(r"\(|\)|AND|OR|WITH|[A-Za-z0-9][A-Za-z0-9.+-]*", expression)
    compact = re.sub(r"\s+", "", expression)
    if "".join(tokens) != compact:
        return False
    position = 0

    def primary() -> bool:
        nonlocal position
        if position >= len(tokens):
            raise ValueError
        if tokens[position] == "(":
            position += 1
            result = parse_or()
            if position >= len(tokens) or tokens[position] != ")":
                raise ValueError
            position += 1
            return result
        token = tokens[position]
        if token in {"AND", "OR", "WITH", ")"}:
            raise ValueError
        position += 1
        result = token in ALLOWED_LICENSE_TOKENS
        if position < len(tokens) and tokens[position] == "WITH":
            position += 1
            if position >= len(tokens) or tokens[position] in {"AND", "OR", "WITH", "(", ")"}:
                raise ValueError
            # Exceptions require their own explicit approval token.
            result = result and tokens[position] in ALLOWED_LICENSE_TOKENS
            position += 1
        return result

    def parse_and() -> bool:
        nonlocal position
        result = primary()
        while position < len(tokens) and tokens[position] == "AND":
            position += 1
            result = primary() and result
        return result

    def parse_or() -> bool:
        nonlocal position
        result = parse_and()
        while position < len(tokens) and tokens[position] == "OR":
            position += 1
            result = parse_and() or result
        return result

    try:
        allowed = parse_or()
    except ValueError:
        return False
    return position == len(tokens) and allowed


def notice_files(root: Path) -> list[Path]:
    if not root.is_dir() or root.is_symlink():
        return []
    values = [
        path for path in root.iterdir()
        if NOTICE_NAME_PATTERN.fullmatch(path.name) and path.is_file() and not path.is_symlink()
    ]
    return sorted(values)


def required_notice(root: Path, relative: str, component: str) -> Path:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise ComplianceError(f"{component} expected license text is missing: {relative}")
    return path


def python_inventory(
    root: Path, version: str, license_source_commit: str
) -> tuple[list[Path], dict[str, object]]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.\d+", version)
    if match is None:
        raise ComplianceError("Python component version is invalid")
    python_minor = f"{match.group(1)}.{match.group(2)}"
    python_notices = [required_notice(root, f"lib/python{python_minor}/LICENSE.txt", "Python")]
    license_root = root / "share" / "licenses" / "python-build-standalone"
    dependency_notices = [
        required_notice(
            license_root,
            name,
            "python-build-standalone bundled dependencies",
        )
        for name in PYTHON_STANDALONE_LICENSE_FILES
    ]
    dependency_package: dict[str, object] = {
        "name": "python-build-standalone bundled dependencies",
        "version": license_source_commit,
        "license": PYTHON_STANDALONE_LICENSE_EXPRESSION,
        "root": license_root,
        "path": license_root.relative_to(root.parent.parent).as_posix(),
        "notices": dependency_notices,
    }
    return python_notices, dependency_package


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def component_version(components: object, key: str) -> str:
    """Read the version from the assembler's hash-bound component projection."""
    if not isinstance(components, dict) or key not in components:
        raise ComplianceError(f"{key} component metadata is unavailable")
    value = components[key]
    if isinstance(value, dict):
        value = value.get("version")
    if not isinstance(value, str) or not value.strip():
        raise ComplianceError(f"{key} component version is invalid")
    return value.strip()


def inventory(payload: Path) -> list[dict[str, object]]:
    librechat = payload / "runtime" / "librechat"
    packages: list[dict[str, object]] = []
    component_roots = (
        ("node", payload / "runtime" / "node", "Node.js"),
        ("python", payload / "runtime" / "python", "Python standalone runtime"),
        ("mongodb", payload / "runtime" / "mongodb", "MongoDB Community Server"),
        ("librechat", librechat, "LibreChat"),
    )
    metadata = json.loads((payload / "release-metadata" / "build.json").read_text(encoding="utf-8"))
    versions = metadata["components"]
    for key, root, name in component_roots:
        if key == "node":
            notices = [required_notice(root, "LICENSE", name)]
        elif key == "python":
            python_component = versions.get("python") if isinstance(versions, dict) else None
            license_source_commit = (
                python_component.get("license_source_commit")
                if isinstance(python_component, dict)
                else None
            )
            if not isinstance(license_source_commit, str) or not re.fullmatch(
                r"[0-9a-f]{40}", license_source_commit
            ):
                raise ComplianceError("Python license-source commit is unavailable")
            notices, python_dependency_package = python_inventory(
                root,
                component_version(versions, key),
                license_source_commit,
            )
        elif key == "mongodb":
            notices = [
                required_notice(root, "LICENSE-Community.txt", name),
                required_notice(root, "THIRD-PARTY-NOTICES", name),
            ]
            optional_mpl = root / "MPL-2"
            if optional_mpl.is_file() and not optional_mpl.is_symlink():
                notices.append(optional_mpl)
        else:
            notices = [required_notice(root, "LICENSE", name)]
        if key == "librechat":
            package = package_json(root / "package.json")
            version = str(package.get("version", "NOASSERTION"))
            license_value = declared_license(package.get("license", package.get("licenses")))
        else:
            version = component_version(versions, key)
            license_value = {
                "node": "MIT",
                "python": "Python-2.0",
                "mongodb": "SSPL-1.0",
            }[key]
        packages.append({
            "name": name, "version": version, "license": license_value, "root": root,
            "path": root.relative_to(payload).as_posix(), "notices": notices,
            "inventory_scope": "physical-runtime",
        })
        if key == "python":
            python_dependency_package["inventory_scope"] = "physical-runtime"
            packages.append(python_dependency_package)
    for relative, root in locked_package_roots(librechat):
        path = root / "package.json"
        package = package_json(path)
        name = str(package["name"])
        version = str(package.get("version", "NOASSERTION"))
        notices = notice_files(root)
        packages.append({
            "name": name,
            "version": version,
            "license": declared_license(package.get("license", package.get("licenses"))),
            "root": root,
            "path": f"runtime/librechat/{relative}",
            "notices": notices,
            "inventory_scope": "physical-runtime",
        })
    packages.extend(browser_inventory(payload))
    return packages


def scan_package_record(payload: Path, package: dict[str, object]) -> dict[str, object]:
    notices = package["notices"]
    if not isinstance(notices, list):
        raise ComplianceError("native package notice inventory is invalid")
    notice_relatives = [path.relative_to(payload).as_posix() for path in notices]
    notice_hashes = {path: sha256_file(payload / path) for path in notice_relatives}
    license_value = str(package["license"])
    record: dict[str, object] = {
        "name": package["name"],
        "version": package["version"],
        "path": package["path"],
        "license": license_value,
        "license_files": notice_relatives,
        "license_file_sha256": notice_hashes,
        "notice_present": bool(notices),
        "allowed": license_allowed(license_value) and bool(notices),
        "inventory_scope": package.get("inventory_scope", "physical-runtime"),
    }
    if "lock_path" in package:
        record["lock_path"] = package["lock_path"]
    return record


def safe_id(index: int, name: str) -> str:
    return f"SPDXRef-Package-{index}-{re.sub(r'[^A-Za-z0-9.-]', '-', name)[:80]}"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def generate(args: argparse.Namespace) -> None:
    payload = args.payload_root.resolve()
    output = args.output_dir.resolve()
    if output != payload / "release-metadata":
        raise ComplianceError("compliance output must be the payload release-metadata directory")
    if not args.mongodb_redistribution_approved.is_file():
        raise ComplianceError("MongoDB redistribution approval is not recorded")
    metadata = json.loads((output / "build.json").read_text(encoding="utf-8"))
    packages = inventory(payload)
    created = __import__("datetime").datetime.fromtimestamp(
        int(metadata["source_date_epoch"]), tz=__import__("datetime").timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    spdx_packages = []
    relationships = []
    scan_packages = []
    notice_sections = []
    for index, package in enumerate(packages, 1):
        spdx_id = safe_id(index, str(package["name"]))
        license_value = str(package["license"])
        notices = package["notices"]
        scan_packages.append(scan_package_record(payload, package))
        spdx_packages.append({
            "SPDXID": spdx_id,
            "name": package["name"],
            "versionInfo": package["version"],
            "packageFileName": package["path"],
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": license_value,
            "copyrightText": "NOASSERTION",
        })
        relationships.append({"spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES", "relatedSpdxElement": spdx_id})
        for notice in notices:
            text = notice.read_text(encoding="utf-8", errors="replace")
            notice_sections.append(f"===== {package['name']} {package['version']} :: {notice.relative_to(payload).as_posix()} =====\n{text.rstrip()}\n")
    failures = [item for item in scan_packages if not item["allowed"]]
    notices_text = "\n".join(notice_sections)
    scan = {
        "schema_version": 1,
        "status": "pass" if not failures else "review_required",
        "notices_sha256": hashlib.sha256(notices_text.encode("utf-8")).hexdigest(),
        "packages": scan_packages,
    }
    sbom = {
        "spdxVersion": "SPDX-2.3", "dataLicense": "CC0-1.0", "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"Viventium-Native-{metadata['arch']}-{metadata['source_commit']}",
        "documentNamespace": f"https://viventium.ai/spdx/native/{metadata['source_commit']}/{metadata['arch']}",
        "creationInfo": {"created": created, "creators": ["Tool: Viventium Native compliance generator"]},
        "packages": spdx_packages, "relationships": relationships,
    }
    atomic_write(output / "native-sbom.spdx.json", json.dumps(sbom, sort_keys=True, separators=(",", ":")) + "\n")
    atomic_write(output / "native-third-party-notices.txt", notices_text)
    atomic_write(output / "native-license-scan.json", json.dumps(scan, sort_keys=True, separators=(",", ":")) + "\n")
    if failures:
        raise ComplianceError(f"{len(failures)} bundled packages require license review")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--payload-root", type=Path, required=True)
    value.add_argument("--output-dir", type=Path, required=True)
    value.add_argument("--mongodb-redistribution-approved", type=Path, required=True)
    return value


if __name__ == "__main__":
    try:
        generate(parser().parse_args())
    except (ComplianceError, OSError, KeyError, TypeError, ValueError) as error:
        print(f"Native compliance generation failed: {error}", file=__import__("sys").stderr)
        raise SystemExit(1)
