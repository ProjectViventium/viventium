#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

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


def load_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"Config file must be a mapping: {path}")
    return data


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
    try:
        clone_repo(origin, target_dir, quiet=snapshot_available)
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
    if not config:
        return components

    selected_names = {"LibreChat"}
    voice_mode = str(config.get("voice", {}).get("mode", "disabled")).strip().lower()
    playground_variant = str(
        config.get("runtime", {}).get("playground_variant", "modern")
    ).strip().lower()

    if playground_variant == "classic":
        selected_names.add("agents-playground")
    elif voice_mode != "disabled":
        selected_names.add("agent-starter-react")

    integrations = config.get("integrations", {}) or {}
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
