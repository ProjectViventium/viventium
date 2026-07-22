#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

SNAPSHOT_MARKER_FILENAME = ".viventium-component.json"
SNAPSHOT_REFRESH_PREFIX = "__REFRESH_PRIVATE_SNAPSHOT__:"
DIRTY_DELETE_FRACTION_LIMIT = 0.2
DIRTY_DELETE_COUNT_LIMIT = 50
BOOTSTRAP_MARKER_PATHS = (
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "client/index.html",
    "api/server/index.js",
    "main.py",
)

DEFAULT_BOOTSTRAP_JOBS = 2
GIT_IDENTITY_TIMEOUT_SECONDS = 15
COMPONENT_SELECTION_PATHS = frozenset(
    {
        ("voice", "mode"),
        ("runtime", "playground_variant"),
        ("integrations", "glasshive", "enabled"),
        ("integrations", "google_workspace", "enabled"),
        ("integrations", "ms365", "enabled"),
        ("integrations", "openclaw", "enabled"),
        ("integrations", "skyvern", "enabled"),
    }
)
COMPONENT_SELECTION_PREFIXES = frozenset(
    path[:depth]
    for path in COMPONENT_SELECTION_PATHS
    for depth in range(1, len(path))
)
YAML_MAPPING_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:[ ]+(.*))?$")
SCP_GIT_URL_RE = re.compile(r"^(?:[^@/:]+@)?(?P<host>[^/:]+):(?P<path>.+)$")


class ComponentSelectionConfig(dict[str, Any]):
    """Selection values plus whether the source contained an actual config mapping."""

    source_has_mapping = False


def run(cmd: list[str], *, cwd: Path | None = None, quiet: bool = False) -> None:
    subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=quiet,
        text=quiet,
    )


def load_lockfile(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _strip_yaml_comment(value: str) -> str:
    quote = ""
    escaped = False
    index = 0
    while index < len(value):
        character = value[index]
        if quote == '"':
            if escaped:
                escaped = False
                index += 1
                continue
            if character == "\\":
                escaped = True
                index += 1
                continue
            if character == quote:
                quote = ""
            index += 1
            continue
        if quote == "'":
            if character == quote:
                if index + 1 < len(value) and value[index + 1] == quote:
                    index += 2
                    continue
                quote = ""
            index += 1
            continue
        if character in {'"', "'"}:
            quote = character
        elif character == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
        index += 1
    if quote:
        raise ValueError("unterminated quoted YAML scalar")
    return value.rstrip()


def _parse_yaml_scalar(value: str) -> Any:
    value = _strip_yaml_comment(value).strip()
    if not value:
        raise ValueError("empty YAML scalar")
    if value.startswith('"'):
        parsed = json.loads(value)
        if not isinstance(parsed, str):
            raise ValueError("component selection scalar must be a string or boolean")
        return parsed
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise ValueError("unterminated single-quoted YAML scalar")
        return value[1:-1].replace("''", "'")
    normalized = value.lower()
    if normalized in {"true", "yes", "on"}:
        return True
    if normalized in {"false", "no", "off"}:
        return False
    if normalized in {"null", "~"}:
        return None
    if any(character in value for character in "{}[]&*!|>`"):
        raise ValueError("unsupported YAML syntax in component selection value")
    return value


def _set_component_selection_value(
    result: dict[str, Any],
    path: tuple[str, ...],
    value: Any,
) -> None:
    if path[-1] == "enabled" and value is not None and not isinstance(value, bool):
        raise ValueError("component enabled selection must be a boolean or null")
    cursor = result
    for path_part in path[:-1]:
        nested = cursor.setdefault(path_part, {})
        if not isinstance(nested, dict):
            raise ValueError("component selection field conflicts with a scalar")
        cursor = nested
    cursor[path[-1]] = value


def load_component_selection_config(path: Path) -> dict[str, Any]:
    """Read the supported component-selection YAML subset without third-party modules.

    Both read-only upgrade inspection and mutating bootstrap use this exact parser. YAML
    constructs that could change a selected component but are outside the supported subset
    fail closed instead of being interpreted differently by two dependency environments.
    """
    result = ComponentSelectionConfig()
    stack: list[tuple[int, str]] = []
    seen: set[tuple[str, ...]] = set()
    document_started = False
    document_closed = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        leading = raw_line[: len(raw_line) - len(raw_line.lstrip())]
        if "\t" in leading:
            raise ValueError("tabs are not supported in canonical YAML indentation")
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        content = _strip_yaml_comment(raw_line[indent:]).rstrip()
        if not content:
            continue
        if content == "---" and indent == 0:
            if document_started or document_closed:
                raise ValueError("multiple YAML documents are not supported")
            document_started = True
            continue
        if content == "..." and indent == 0:
            if document_closed:
                raise ValueError("multiple YAML document endings are not supported")
            document_closed = True
            continue
        if document_closed:
            raise ValueError("content after a YAML document end is not supported")
        document_started = True
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent_path = tuple(item[1] for item in stack)
        if parent_path in COMPONENT_SELECTION_PATHS:
            raise ValueError("component selection scalars cannot contain nested YAML")
        match = YAML_MAPPING_KEY_RE.fullmatch(content)
        if not match:
            if not parent_path or parent_path in COMPONENT_SELECTION_PREFIXES:
                raise ValueError("unsupported YAML syntax in component selection structure")
            continue
        result.source_has_mapping = True
        key = match.group(1)
        current_path = parent_path + (key,)
        raw_value = match.group(2)
        is_selection_path = current_path in COMPONENT_SELECTION_PATHS
        is_selection_prefix = current_path in COMPONENT_SELECTION_PREFIXES
        if (is_selection_path or is_selection_prefix) and current_path in seen:
            raise ValueError("duplicate component selection field")
        if is_selection_path or is_selection_prefix:
            seen.add(current_path)
        if raw_value is None or not raw_value.strip():
            if is_selection_path:
                _set_component_selection_value(result, current_path, None)
                stack.append((indent, key))
                continue
            stack.append((indent, key))
            continue
        if is_selection_prefix:
            raise ValueError("component selection containers must use block mappings")
        if is_selection_path:
            _set_component_selection_value(
                result,
                current_path,
                _parse_yaml_scalar(raw_value),
            )
    return result


def load_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    return load_component_selection_config(path)


def resolve_bootstrap_jobs(component_count: int, requested_jobs: int | None = None) -> int:
    if component_count <= 1:
        return 1

    if requested_jobs is None:
        raw_jobs = os.environ.get("VIVENTIUM_BOOTSTRAP_JOBS", "").strip()
        if raw_jobs:
            try:
                requested_jobs = int(raw_jobs)
            except ValueError:
                requested_jobs = DEFAULT_BOOTSTRAP_JOBS
        else:
            requested_jobs = DEFAULT_BOOTSTRAP_JOBS

    if requested_jobs is None or requested_jobs < 1:
        requested_jobs = 1

    return max(1, min(component_count, requested_jobs))


def repo_has_ref(repo_dir: Path, ref: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def resolve_ref(repo_dir: Path, ref: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", f"{ref}^{{commit}}"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def repo_is_dirty(repo_dir: Path) -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    return bool(result.stdout.strip())


def tracked_file_count(repo_dir: Path) -> int:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_dir,
        capture_output=True,
        check=True,
    )
    if not result.stdout:
        return 0
    return result.stdout.count(b"\0")


def repo_tracks_path(repo_dir: Path, rel_path: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"HEAD:{rel_path}"],
        cwd=repo_dir,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def evaluate_dirty_checkout(repo_dir: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    deleted_paths: list[str] = []
    for line in result.stdout.splitlines():
        status = line[:2]
        if "D" not in status:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[-1]
        deleted_paths.append(path)

    tracked_total = tracked_file_count(repo_dir)
    missing_markers = [
        rel_path
        for rel_path in BOOTSTRAP_MARKER_PATHS
        if repo_tracks_path(repo_dir, rel_path) and not (repo_dir / rel_path).exists()
    ]
    deleted_count = len(deleted_paths)
    catastrophic = bool(missing_markers)
    if tracked_total > 0 and deleted_count > 0:
        catastrophic = catastrophic or (
            deleted_count >= DIRTY_DELETE_COUNT_LIMIT
            and (deleted_count / tracked_total) >= DIRTY_DELETE_FRACTION_LIMIT
        )

    return {
        "deleted_count": deleted_count,
        "tracked_total": tracked_total,
        "missing_markers": missing_markers,
        "sample_deleted": deleted_paths[:5],
        "catastrophic": catastrophic,
    }


def ensure_dirty_checkout_is_bootable(repo_dir: Path, name: str) -> None:
    summary = evaluate_dirty_checkout(repo_dir)
    if not summary["catastrophic"]:
        return

    details: list[str] = []
    if summary["missing_markers"]:
        details.append(f"missing bootstrap files: {', '.join(summary['missing_markers'])}")
    if summary["deleted_count"]:
        details.append(
            f"tracked deletions: {summary['deleted_count']}/{summary['tracked_total'] or 0}"
        )
    if summary["sample_deleted"]:
        details.append(f"examples: {', '.join(summary['sample_deleted'])}")
    detail_text = "; ".join(details) if details else "component worktree is not bootable"
    raise SystemExit(
        f"Component {name} has a catastrophically dirty checkout; refusing to bootstrap. {detail_text}"
    )


def is_commit_sha(ref: str) -> bool:
    return len(ref) == 40 and all(ch in "0123456789abcdefABCDEF" for ch in ref)


def is_local_origin(origin: str) -> bool:
    if origin.startswith("git@"):
        return False
    parsed = urlparse(origin)
    if parsed.scheme in {"http", "https", "ssh", "git"}:
        return False
    if parsed.scheme == "file":
        return True
    return Path(origin).expanduser().exists()


def resolve_origin_path(origin: str) -> Path | None:
    parsed = urlparse(origin)
    if parsed.scheme == "file":
        return Path(parsed.path).expanduser().resolve()
    if parsed.scheme:
        return None
    candidate = Path(origin).expanduser()
    if candidate.exists():
        return candidate.resolve()
    return None


def canonical_repository_identity(
    origin: str,
    *,
    base_dir: Path | None = None,
) -> tuple[str, ...] | None:
    """Return a transport-independent repository identity without network access."""
    raw_origin = origin.strip()
    if not raw_origin:
        return None

    scp_match = SCP_GIT_URL_RE.fullmatch(raw_origin) if "://" not in raw_origin else None
    if scp_match and ("@" in raw_origin or "." in scp_match.group("host")):
        host = scp_match.group("host").lower().rstrip(".")
        repo_path = unquote(scp_match.group("path")).strip("/")
        if repo_path.lower().endswith(".git"):
            repo_path = repo_path[:-4]
        if not host or not repo_path:
            return None
        if host == "github.com":
            repo_path = repo_path.lower()
        return ("remote", host, repo_path)

    parsed = urlparse(raw_origin)
    if parsed.scheme in {"http", "https", "ssh", "git"}:
        if parsed.params or parsed.query or parsed.fragment:
            return None
        host = (parsed.hostname or "").lower().rstrip(".")
        repo_path = unquote(parsed.path).strip("/")
        if repo_path.lower().endswith(".git"):
            repo_path = repo_path[:-4]
        if not host or not repo_path:
            return None
        if any(part in {"", ".", ".."} for part in repo_path.split("/")):
            return None
        try:
            port = parsed.port
        except ValueError:
            return None
        default_ports = {"http": 80, "https": 443, "ssh": 22, "git": 9418}
        host_identity = host if port in {None, default_ports[parsed.scheme]} else f"{host}:{port}"
        if host == "github.com":
            repo_path = repo_path.lower()
        return ("remote", host_identity, repo_path)
    if parsed.scheme == "file":
        if parsed.hostname not in {None, "", "localhost"}:
            return None
        local_path = Path(unquote(parsed.path)).expanduser()
    elif parsed.scheme:
        return None
    else:
        local_path = Path(raw_origin).expanduser()
        if not local_path.is_absolute() and base_dir is not None:
            local_path = base_dir / local_path
    try:
        return ("local", str(local_path.resolve(strict=False)))
    except OSError:
        return None


def component_origin_status(
    repo_dir: Path,
    expected_origin: object,
    *,
    expected_base_dir: Path | None = None,
) -> str | None:
    """Describe why an existing checkout's origin cannot be trusted, if applicable."""
    if not isinstance(expected_origin, str) or not expected_origin.strip():
        return "invalid_origin"
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_IDENTITY_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return "unverifiable_origin"
    if result.returncode != 0 or not result.stdout.strip():
        return "missing_origin"
    expected_identity = canonical_repository_identity(
        expected_origin,
        base_dir=expected_base_dir,
    )
    actual_identity = canonical_repository_identity(
        result.stdout.strip(),
        base_dir=repo_dir,
    )
    if expected_identity is None or actual_identity is None:
        return "unverifiable_origin"
    if expected_identity != actual_identity:
        return "origin_mismatch"
    return None


def ensure_component_origin(repo_root: Path, repo_dir: Path, component: dict[str, Any]) -> None:
    status = component_origin_status(
        repo_dir,
        component.get("_locked_origin", component.get("origin")),
        expected_base_dir=repo_root,
    )
    if status is None:
        return
    name = str(component.get("name") or component.get("path") or "component")
    if status == "invalid_origin":
        raise SystemExit(f"Component {name} has no valid locked origin; refusing to bootstrap")
    if status == "missing_origin":
        raise SystemExit(f"Component {name} has no origin remote; refusing to bootstrap")
    if status == "origin_mismatch":
        raise SystemExit(f"Component {name} has an unrelated origin; refusing to bootstrap")
    raise SystemExit(f"Component {name} has an unverifiable origin; refusing to bootstrap")


def ensure_remote(repo_dir: Path, remote_name: str, remote_url: str) -> None:
    result = subprocess.run(
        ["git", "remote", "get-url", remote_name],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        run(["git", "remote", "add", remote_name, remote_url], cwd=repo_dir)
        return
    if result.stdout.strip() != remote_url:
        run(["git", "remote", "set-url", remote_name, remote_url], cwd=repo_dir)


def fetch_ref_from_source(repo_dir: Path, origin: str, ref: str, *, quiet: bool = False) -> bool:
    origin_path = resolve_origin_path(origin)
    if origin_path and origin_path == repo_dir.resolve():
        return False
    remote_name = "viventium-lock-origin"
    ensure_remote(repo_dir, remote_name, origin)
    run(["git", "fetch", "--force", remote_name, ref], cwd=repo_dir, quiet=quiet)
    return True


def clone_repo(origin: str, target_dir: Path, *, quiet: bool = False) -> None:
    cmd = ["git", "clone"]
    if not is_local_origin(origin):
        cmd.extend(["--filter=blob:none"])
    cmd.extend([origin, str(target_dir)])
    run(cmd, quiet=quiet)


def checkout_ref(repo_dir: Path, *args: str, quiet: bool = False) -> None:
    run(
        ["git", "-c", "advice.detachedHead=false", "checkout", "--force", *args],
        cwd=repo_dir,
        quiet=quiet,
    )


def is_empty_placeholder_dir(path: Path) -> bool:
    return path.is_dir() and not any(path.iterdir())


def is_bootable_vendored_component_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    return any((path / marker).exists() for marker in BOOTSTRAP_MARKER_PATHS)


def clone_component_checkout(
    repo_root: Path,
    name: str,
    origin: str,
    ref: str,
    target_dir: Path,
    *,
    branch_ref: bool,
    snapshot_available: bool,
    component: dict[str, Any],
) -> str:
    locked_origin = component.get("_locked_origin")
    locked_identity: tuple[str, ...] | None = None
    if locked_origin is not None:
        if not isinstance(locked_origin, str):
            raise SystemExit(f"Component {name} has no valid locked origin; refusing to bootstrap")
        locked_identity = canonical_repository_identity(locked_origin, base_dir=repo_root)
        if locked_identity is None:
            raise SystemExit(f"Component {name} has no valid locked origin; refusing to bootstrap")
    try:
        clone_repo(origin, target_dir, quiet=snapshot_available)
        if locked_identity is not None:
            persisted_origin = locked_identity[1] if locked_identity[0] == "local" else locked_origin
            ensure_remote(target_dir, "origin", persisted_origin)
        if branch_ref:
            if repo_has_ref(target_dir, ref):
                checkout_ref(target_dir, ref, quiet=snapshot_available)
            else:
                fetch_ref_from_source(target_dir, origin, ref, quiet=snapshot_available)
                checkout_ref(target_dir, "-B", ref, "FETCH_HEAD", quiet=snapshot_available)
        else:
            checkout_ref(target_dir, ref, quiet=snapshot_available)
        return f"cloned {name} -> {target_dir}"
    except subprocess.CalledProcessError:
        if snapshot_available:
            return extract_private_snapshot(
                repo_root,
                component,
                target_dir,
                "missing-locked-ref-during-clone",
            )
        raise


def clone_or_update_component(
    repo_root: Path,
    component: dict[str, Any],
    update_existing: bool,
    *,
    prefer_existing_checkout_head: bool = False,
) -> str:
    name = component["name"]
    origin = component["origin"]
    ref = component["ref"]
    target_dir = repo_root / component["path"]
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    branch_ref = not is_commit_sha(ref)
    snapshot_available = can_use_private_snapshot(repo_root, component)

    if not target_dir.exists():
        return clone_component_checkout(
            repo_root,
            name,
            origin,
            ref,
            target_dir,
            branch_ref=branch_ref,
            snapshot_available=snapshot_available,
            component=component,
        )

    if is_empty_placeholder_dir(target_dir):
        shutil.rmtree(target_dir)
        return clone_component_checkout(
            repo_root,
            name,
            origin,
            ref,
            target_dir,
            branch_ref=branch_ref,
            snapshot_available=snapshot_available,
            component=component,
        )

    if (target_dir / ".git").exists():
        ensure_component_origin(repo_root, target_dir, component)
    snapshot_validation = validate_private_snapshot_install(repo_root, component, target_dir)
    if snapshot_validation is not None:
        if snapshot_validation.startswith(SNAPSHOT_REFRESH_PREFIX):
            refresh_reason = snapshot_validation.removeprefix(SNAPSHOT_REFRESH_PREFIX)
            return extract_private_snapshot(
                repo_root,
                component,
                target_dir,
                f"snapshot-refresh-{refresh_reason}",
            )
        return snapshot_validation
    if not (target_dir / ".git").exists():
        if snapshot_available:
            return extract_private_snapshot(
                repo_root,
                component,
                target_dir,
                "existing-non-git-path",
            )
        if is_bootable_vendored_component_dir(target_dir):
            return f"kept vendored checkout for {name} -> {target_dir}"
        raise SystemExit(f"Existing path is not a git repo: {target_dir}")

    if repo_is_dirty(target_dir):
        ensure_dirty_checkout_is_bootable(target_dir, name)
        return f"kept local dirty checkout for {name} -> {current_head(target_dir)}"

    current_ref = current_head(target_dir)
    current_branch = current_branch_name(target_dir)
    if prefer_existing_checkout_head and current_branch:
        return f"kept existing clean branch checkout for {name} -> {current_ref} ({current_branch})"

    try:
        if repo_has_ref(target_dir, ref):
            resolved_ref = resolve_ref(target_dir, ref)
            if not branch_ref and current_ref == resolved_ref:
                return f"kept existing clean checkout for {name} -> {resolved_ref}"
            if update_existing and branch_ref:
                fetched = fetch_ref_from_source(target_dir, origin, ref, quiet=snapshot_available)
                if fetched:
                    checkout_ref(target_dir, "-B", ref, "FETCH_HEAD", quiet=snapshot_available)
                else:
                    checkout_ref(target_dir, ref, quiet=snapshot_available)
            elif branch_ref:
                checkout_ref(target_dir, ref, quiet=snapshot_available)
            else:
                checkout_ref(target_dir, ref, quiet=snapshot_available)
            return f"checked out {name} -> {ref}"

        if not update_existing:
            raise SystemExit(f"Missing required ref for existing repo {name}: {ref}")

        fetched = fetch_ref_from_source(target_dir, origin, ref, quiet=snapshot_available)
        if not fetched:
            raise SystemExit(f"Missing required local ref for existing repo {name}: {ref}")
        if branch_ref:
            checkout_ref(target_dir, "-B", ref, "FETCH_HEAD", quiet=snapshot_available)
        else:
            checkout_ref(target_dir, ref, quiet=snapshot_available)
        return f"updated {name} -> {ref}"
    except subprocess.CalledProcessError:
        if snapshot_available:
            return extract_private_snapshot(
                repo_root,
                component,
                target_dir,
                "missing-locked-ref-during-update",
            )
        raise


def current_head(repo_dir: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def current_branch_name(repo_dir: Path) -> str | None:
    result = subprocess.run(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    branch = result.stdout.strip()
    if result.returncode != 0 or not branch:
        return None
    return branch


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_marker_path(target_dir: Path) -> Path:
    return target_dir / SNAPSHOT_MARKER_FILENAME


def load_snapshot_marker(target_dir: Path) -> dict[str, Any] | None:
    marker = snapshot_marker_path(target_dir)
    if not marker.is_file():
        return None
    data = json.loads(marker.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def get_private_snapshot(
    repo_root: Path, component: dict[str, Any]
) -> tuple[dict[str, Any], Path] | tuple[None, None]:
    payload = component.get("private_snapshot")
    if not isinstance(payload, dict):
        return None, None
    raw_path = str(payload.get("path") or "").strip()
    if not raw_path:
        return None, None
    snapshot_path = Path(raw_path).expanduser()
    if not snapshot_path.is_absolute():
        snapshot_path = repo_root / snapshot_path
    return payload, snapshot_path.resolve()


def can_use_private_snapshot(repo_root: Path, component: dict[str, Any]) -> bool:
    _payload, snapshot_path = get_private_snapshot(repo_root, component)
    return snapshot_path is not None and snapshot_path.is_file()


def validate_snapshot_archive(snapshot_path: Path, payload: dict[str, Any] | None) -> str:
    checksum = file_sha256(snapshot_path)
    expected = str((payload or {}).get("sha256") or "").strip().lower()
    if expected and checksum.lower() != expected:
        raise SystemExit(
            f"Snapshot checksum mismatch for {snapshot_path}: expected {expected}, got {checksum}"
        )
    return checksum


def _safe_extract_tarball(archive_path: Path, target_dir: Path) -> None:
    target_root = target_dir.resolve()
    with tarfile.open(archive_path, "r:*") as archive:
        members = archive.getmembers()
        for member in members:
            member_path = (target_dir / member.name).resolve()
            if member_path != target_root and target_root not in member_path.parents:
                raise SystemExit(f"Unsafe path in snapshot archive {archive_path}: {member.name}")
        filtered_members = [
            member
            for member in members
            if "__MACOSX" not in Path(member.name).parts
            and not any(part.startswith("._") for part in Path(member.name).parts)
        ]
        try:
            extract_kwargs: dict[str, Any] = {"path": target_dir, "members": filtered_members}
            if "filter" in tarfile.TarFile.extractall.__code__.co_varnames:
                extract_kwargs["filter"] = "data"
            archive.extractall(**extract_kwargs)
        except tarfile.TarError:
            archive.extractall(target_dir, members=filtered_members)


def _prune_external_snapshot_symlinks(target_dir: Path) -> None:
    target_root = target_dir.resolve()
    skip_dirs = {"node_modules", ".git", ".venv", ".next", "__pycache__"}
    for current_root, dirnames, filenames in os.walk(target_dir, topdown=True, followlinks=False):
        root_path = Path(current_root)
        entries = [root_path / name for name in [*dirnames, *filenames]]
        for path in entries:
            if not path.is_symlink():
                continue
            try:
                resolved = path.resolve(strict=False)
            except OSError:
                path.unlink(missing_ok=True)
                continue
            if resolved != target_root and target_root not in resolved.parents:
                path.unlink(missing_ok=True)
        dirnames[:] = [
            name
            for name in dirnames
            if name not in skip_dirs and not (root_path / name).is_symlink()
        ]


def prune_snapshot_noise(target_dir: Path) -> None:
    for path in target_dir.rglob("._*"):
        if path.is_file() or path.is_symlink():
            path.unlink(missing_ok=True)
    for path in sorted(target_dir.rglob("__MACOSX"), reverse=True):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            path.unlink(missing_ok=True)
    _prune_external_snapshot_symlinks(target_dir)


def replace_existing_component_dir(target_dir: Path) -> None:
    if not target_dir.exists() and not target_dir.is_symlink():
        return
    if target_dir.is_symlink() or target_dir.is_file():
        target_dir.unlink(missing_ok=True)
        return
    dependency_trees = (
        target_dir / "node_modules",
        target_dir / "client" / "node_modules",
        target_dir / "packages" / "api" / "node_modules",
        target_dir / "packages" / "client" / "node_modules",
        target_dir / "packages" / "data-provider" / "node_modules",
        target_dir / "packages" / "data-schemas" / "node_modules",
    )
    if any(path.exists() for path in dependency_trees):
        subprocess.run(["/bin/rm", "-rf", str(target_dir)], check=False)
        if not target_dir.exists() and not target_dir.is_symlink():
            return
    try:
        shutil.rmtree(target_dir)
        return
    except FileNotFoundError:
        return
    except OSError:
        if not target_dir.exists() and not target_dir.is_symlink():
            return
        backup_dir = target_dir.parent / f".{target_dir.name}.stale-{os.getpid()}-{time.time_ns()}"
        try:
            os.replace(target_dir, backup_dir)
        except FileNotFoundError:
            return
        shutil.rmtree(backup_dir, ignore_errors=True)


def extract_private_snapshot(
    repo_root: Path,
    component: dict[str, Any],
    target_dir: Path,
    reason: str,
) -> str:
    payload, snapshot_path = get_private_snapshot(repo_root, component)
    if snapshot_path is None or payload is None or not snapshot_path.is_file():
        raise SystemExit(f"No private snapshot available for {component['name']}")

    checksum = validate_snapshot_archive(snapshot_path, payload)
    if target_dir.exists():
        replace_existing_component_dir(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    _safe_extract_tarball(snapshot_path, target_dir)
    prune_snapshot_noise(target_dir)
    snapshot_marker_path(target_dir).write_text(
        json.dumps(
            {
                "name": component["name"],
                "ref": component["ref"],
                "snapshot_path": str(snapshot_path.relative_to(repo_root)),
                "snapshot_sha256": checksum,
                "reason": reason,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return f"restored private snapshot for {component['name']} -> {target_dir}"


def validate_private_snapshot_install(
    repo_root: Path,
    component: dict[str, Any],
    target_dir: Path,
) -> str | None:
    marker = load_snapshot_marker(target_dir)
    payload, snapshot_path = get_private_snapshot(repo_root, component)
    if marker is None:
        return None
    if payload is None or snapshot_path is None or not snapshot_path.is_file():
        raise SystemExit(
            f"Snapshot-installed component {component['name']} is missing its snapshot archive"
        )
    prune_snapshot_noise(target_dir)
    if marker.get("name") != component["name"]:
        raise SystemExit(f"Snapshot marker name mismatch for {component['name']}")
    if marker.get("ref") != component["ref"]:
        return f"{SNAPSHOT_REFRESH_PREFIX}ref-mismatch"
    checksum = validate_snapshot_archive(snapshot_path, payload)
    marker_snapshot_path = str(marker.get("snapshot_path") or "").strip()
    expected_snapshot_path = str(snapshot_path.relative_to(repo_root))
    if marker_snapshot_path and marker_snapshot_path != expected_snapshot_path:
        return f"{SNAPSHOT_REFRESH_PREFIX}snapshot-path-mismatch"
    marker_checksum = str(marker.get("snapshot_sha256") or "").strip().lower()
    if marker_checksum and marker_checksum != checksum.lower():
        return f"{SNAPSHOT_REFRESH_PREFIX}checksum-mismatch"
    return f"validated private snapshot for {component['name']} -> {component['ref']}"


def validate_component(
    repo_root: Path,
    component: dict[str, Any],
    *,
    prefer_existing_checkout_head: bool = False,
) -> str:
    name = component["name"]
    ref = component["ref"]
    target_dir = repo_root / component["path"]

    if not target_dir.exists():
        raise SystemExit(f"Missing component directory: {target_dir}")
    if (target_dir / ".git").exists():
        ensure_component_origin(repo_root, target_dir, component)
    snapshot_validation = validate_private_snapshot_install(repo_root, component, target_dir)
    if snapshot_validation is not None:
        if snapshot_validation.startswith(SNAPSHOT_REFRESH_PREFIX):
            refresh_reason = snapshot_validation.removeprefix(SNAPSHOT_REFRESH_PREFIX)
            raise SystemExit(
                f"Snapshot-installed component {name} requires refresh: {refresh_reason}"
            )
        return snapshot_validation
    if not (target_dir / ".git").exists():
        if can_use_private_snapshot(repo_root, component):
            raise SystemExit(
                f"Snapshot-installed component {name} requires refresh: existing-non-git-path"
            )
        if is_bootable_vendored_component_dir(target_dir):
            return f"validated vendored checkout for {name} -> {target_dir}"
        raise SystemExit(f"Existing path is not a git repo: {target_dir}")
    if repo_is_dirty(target_dir):
        ensure_dirty_checkout_is_bootable(target_dir, name)
        return f"validated local dirty checkout for {name} -> {current_head(target_dir)}"
    head = current_head(target_dir)
    current_branch = current_branch_name(target_dir)
    if prefer_existing_checkout_head and current_branch:
        return f"validated existing clean branch checkout for {name} -> {head} ({current_branch})"
    if not repo_has_ref(target_dir, ref):
        raise SystemExit(f"Missing required ref for existing repo {name}: {ref}")

    resolved = resolve_ref(target_dir, ref)
    if head != resolved:
        raise SystemExit(f"Component {name} is not pinned to {ref} (current HEAD {head}, resolved {resolved})")

    return f"validated {name} -> {ref}"


def select_components(components: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    if not config and not getattr(config, "source_has_mapping", False):
        config = {"voice": {"mode": "local"}, "runtime": {"playground_variant": "modern"}}

    selected_names = {"LibreChat"}
    voice_mode = str(config.get("voice", {}).get("mode", "disabled")).strip().lower()
    playground_variant = str(
        config.get("runtime", {}).get("playground_variant", "modern")
    ).strip().lower()

    if voice_mode == "disabled":
        pass
    elif playground_variant == "classic":
        selected_names.add("agents-playground")
    else:
        selected_names.add("agent-starter-react")

    integrations = config.get("integrations", {}) or {}
    if integrations.get("glasshive", {}).get("enabled"):
        selected_names.add("GlassHive")
    if integrations.get("google_workspace", {}).get("enabled"):
        selected_names.add("google_workspace_mcp")
    if integrations.get("ms365", {}).get("enabled"):
        selected_names.add("ms-365-mcp-server")
    if integrations.get("openclaw", {}).get("enabled"):
        selected_names.add("openclaw")
    if integrations.get("skyvern", {}).get("enabled"):
        selected_names.add("skyvern-source")

    return [component for component in components if component.get("name") in selected_names]


def apply_local_origin_overrides(
    components: list[dict[str, Any]], source_root: Path | None
) -> list[dict[str, Any]]:
    if source_root is None:
        return components

    resolved_root = source_root.expanduser().resolve()
    overridden: list[dict[str, Any]] = []
    for component in components:
        local_candidate = resolved_root / str(component.get("path", "")).strip()
        if (local_candidate / ".git").exists():
            updated = dict(component)
            updated["_locked_origin"] = component.get("origin")
            updated["origin"] = str(local_candidate)
            overridden.append(updated)
        else:
            overridden.append(component)
    return overridden


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch pinned public component repos.")
    parser.add_argument("--repo-root", required=True, help="Root of the public Viventium repo")
    parser.add_argument(
        "--lock-file",
        default="components.lock.json",
        help="Lock file path relative to repo root or absolute path",
    )
    parser.add_argument(
        "--no-update-existing",
        action="store_true",
        help="Do not fetch refs for existing repos that are missing the pinned commit",
    )
    parser.add_argument(
        "--config",
        help="Optional config.yaml used to select only the components needed for this install",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Verify selected component directories already exist at the pinned refs without cloning",
    )
    parser.add_argument(
        "--prefer-existing-checkout-head",
        action="store_true",
        help=(
            "For local runtime commands, keep an existing clean named-branch checkout "
            "instead of forcing the lockfile ref."
        ),
    )
    parser.add_argument(
        "--jobs",
        type=int,
        help=(
            "Maximum number of component clone/update jobs to run in parallel. "
            "Defaults to a low-risk shared-path limit."
        ),
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()
    lock_file = Path(args.lock_file).expanduser()
    if not lock_file.is_absolute():
        lock_file = repo_root / lock_file
    payload = load_lockfile(lock_file)
    config_path = Path(args.config).expanduser().resolve() if args.config else None
    config = load_config(config_path)
    source_root_env = os.environ.get("VIVENTIUM_COMPONENTS_SOURCE_ROOT", "").strip()
    source_root = Path(source_root_env) if source_root_env else None

    components = select_components(payload.get("components", []), config)
    components = apply_local_origin_overrides(components, source_root)

    if args.validate_only:
        for component in components:
            print(
                validate_component(
                    repo_root,
                    component,
                    prefer_existing_checkout_head=args.prefer_existing_checkout_head,
                )
            )
        return

    jobs = resolve_bootstrap_jobs(len(components), args.jobs)
    if jobs == 1:
        for component in components:
            print(
                clone_or_update_component(
                    repo_root,
                    component,
                    not args.no_update_existing,
                    prefer_existing_checkout_head=args.prefer_existing_checkout_head,
                )
            )
        return

    with ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = [
            executor.submit(
                clone_or_update_component,
                repo_root,
                component,
                not args.no_update_existing,
                prefer_existing_checkout_head=args.prefer_existing_checkout_head,
            )
            for component in components
        ]
        for future in futures:
            print(future.result())


if __name__ == "__main__":
    main()
