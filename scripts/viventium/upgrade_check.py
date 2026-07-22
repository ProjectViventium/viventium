#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
PREVIOUS_DONT_WRITE_BYTECODE = sys.dont_write_bytecode
sys.dont_write_bytecode = True
try:
    from bootstrap_components import (  # noqa: E402
        apply_local_origin_overrides,
        canonical_repository_identity,
        component_origin_status,
        load_component_selection_config,
        select_components,
    )
finally:
    sys.dont_write_bytecode = PREVIOUS_DONT_WRITE_BYTECODE


GIT_TIMEOUT_SECONDS = 15
FULL_GIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
HELPER_RELATIVE_PATH = Path("apps/macos/ViventiumHelper")
HELPER_BINARY_NAME = "ViventiumHelper-universal"


def run_git(repo: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    command = ["git", "-C", str(repo), *args]
    try:
        return subprocess.run(
            command,
            check=check,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(command, 124, stdout="", stderr="git_command_failed")
    except (OSError, subprocess.SubprocessError):
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="git_command_failed")


def git_output(repo: Path, *args: str) -> str:
    proc = run_git(repo, *args)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def current_branch(repo: Path) -> str:
    return git_output(repo, "rev-parse", "--abbrev-ref", "HEAD") or "unknown"


def _managed_component_prefixes(repo: Path) -> tuple[str, ...]:
    try:
        payload = json.loads((repo / "components.lock.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return ()
    components = payload.get("components") if isinstance(payload, dict) else None
    if not isinstance(components, list):
        return ()
    prefixes: list[str] = []
    for component in components:
        rel_path = component.get("path") if isinstance(component, dict) else None
        if not isinstance(rel_path, str) or safe_component_path(repo, rel_path) is None:
            continue
        prefixes.append(rel_path.rstrip("/") + "/")
    return tuple(prefixes)


def tracked_dirty(repo: Path) -> bool:
    proc = run_git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=normal")
    # A checkout whose state cannot be read is not safe to upgrade.
    if proc.returncode != 0:
        return True
    managed_prefixes = _managed_component_prefixes(repo)
    for entry in proc.stdout.split("\0"):
        if not entry:
            continue
        status = entry[:2]
        path = entry[3:] if len(entry) > 3 else ""
        if status == "??" and any(
            path == prefix.rstrip("/") or path.startswith(prefix)
            for prefix in managed_prefixes
        ):
            continue
        return True
    return False


def count_lines(value: str) -> int:
    return len([line for line in value.splitlines() if line.strip()])


def git_line_count(repo: Path, *args: str) -> int | None:
    proc = run_git(repo, *args)
    return count_lines(proc.stdout) if proc.returncode == 0 else None


def commit_exists(repo: Path, commit: str) -> bool | None:
    if not commit:
        return False
    proc = run_git(repo, "cat-file", "-e", f"{commit}^{{commit}}")
    if proc.returncode == 0:
        return True
    if proc.stderr == "git_command_failed":
        return None
    return False


def observe_remote(repo: Path, branch: str) -> dict[str, Any]:
    remote_proc = run_git(repo, "config", "--get", f"branch.{branch}.remote")
    remote = remote_proc.stdout.strip() if remote_proc.returncode == 0 else ""
    merge_proc = run_git(repo, "config", "--get", f"branch.{branch}.merge")
    merge_ref = merge_proc.stdout.strip() if merge_proc.returncode == 0 else ""
    if not remote or not merge_ref.startswith("refs/heads/"):
        return {
            "upstream": "<configured-upstream>",
            "remote_head": "",
            "ahead": 0,
            "behind": 0,
            "history_complete": False,
            "error": "remote_unavailable",
        }
    remote_result = run_git(repo, "ls-remote", "--exit-code", remote, merge_ref)
    if remote_result.returncode != 0:
        return {
            "upstream": "<configured-upstream>",
            "remote_head": "",
            "ahead": 0,
            "behind": 0,
            "history_complete": False,
            "error": "remote_unavailable",
        }
    remote_head = remote_result.stdout.split()[0] if remote_result.stdout.split() else ""
    local_head = git_output(repo, "rev-parse", "HEAD")
    upstream = "<configured-upstream>"
    if not FULL_GIT_SHA_RE.fullmatch(remote_head) or not FULL_GIT_SHA_RE.fullmatch(local_head):
        return {
            "upstream": upstream,
            "remote_head": "",
            "ahead": 0,
            "behind": 0,
            "history_complete": False,
            "error": "remote_unavailable",
        }
    if remote_head == local_head:
        return {
            "upstream": upstream,
            "remote_head": remote_head,
            "ahead": 0,
            "behind": 0,
            "history_complete": True,
            "error": "",
        }
    remote_commit_exists = commit_exists(repo, remote_head)
    if remote_commit_exists is None:
        return {
            "upstream": upstream,
            "remote_head": remote_head,
            "ahead": 0,
            "behind": 0,
            "history_complete": False,
            "error": "remote_unavailable",
        }
    if remote_commit_exists:
        ahead = git_line_count(repo, "rev-list", f"{remote_head}..HEAD")
        behind = git_line_count(repo, "rev-list", f"HEAD..{remote_head}")
        if ahead is None or behind is None:
            return {
                "upstream": upstream,
                "remote_head": remote_head,
                "ahead": 0,
                "behind": 0,
                "history_complete": False,
                "error": "remote_unavailable",
            }
        return {
            "upstream": upstream,
            "remote_head": remote_head,
            "ahead": ahead,
            "behind": behind,
            "history_complete": True,
            "error": "",
        }
    return {
        "upstream": upstream,
        "remote_head": remote_head,
        "ahead": 0,
        "behind": 1,
        "history_complete": False,
        "error": "",
    }


def safe_component_path(repo: Path, rel_path: str) -> Path | None:
    """Resolve a canonical component path without permitting repository escape."""
    if not rel_path or "\\" in rel_path:
        return None
    posix_path = PurePosixPath(rel_path)
    if posix_path.is_absolute() or posix_path.as_posix() != rel_path or rel_path == ".":
        return None
    if any(part in {"", ".", ".."} for part in posix_path.parts):
        return None
    repo_root = repo.resolve()
    candidate = (repo_root / Path(*posix_path.parts)).resolve(strict=False)
    try:
        candidate.relative_to(repo_root)
    except ValueError:
        return None
    return candidate


def component_alignment(
    repo: Path,
    config_file: Path | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    lock_path = repo / "components.lock.json"
    if not lock_path.exists():
        return (
            [
                {
                    "name": "components.lock.json",
                    "status": "missing",
                    "expected": "valid component lock",
                    "actual": "",
                }
            ],
            [],
        )
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception:
        return (
            [{"name": "components.lock.json", "status": "invalid", "expected": "", "actual": ""}],
            [],
        )
    if not isinstance(payload, dict):
        return (
            [
                {
                    "name": "components.lock.json",
                    "status": "invalid",
                    "expected": "component lock object",
                    "actual": type(payload).__name__,
                }
            ],
            [],
        )
    components = payload.get("components")
    if not isinstance(components, list):
        return (
            [
                {
                    "name": "components.lock.json",
                    "status": "invalid_components",
                    "expected": "components array",
                    "actual": type(components).__name__,
                }
            ],
            [],
        )
    try:
        selection_config = (
            load_component_selection_config(config_file) if config_file is not None else {}
        )
        components = select_components(components, selection_config)
    except (Exception, SystemExit) as exc:
        return (
            [
                {
                    "name": "config.yaml",
                    "status": "component_selection_failed",
                    "expected": "valid component selection config",
                    "actual": type(exc).__name__,
                }
            ],
            [],
        )
    source_root_value = os.environ.get("VIVENTIUM_COMPONENTS_SOURCE_ROOT", "").strip()
    source_root = Path(source_root_value) if source_root_value else None
    components = apply_local_origin_overrides(components, source_root)
    blockers: list[dict[str, str]] = []
    refresh_required: list[dict[str, str]] = []
    for index, component in enumerate(components):
        if not isinstance(component, dict):
            blockers.append(
                {
                    "name": f"components[{index}]",
                    "status": "invalid_entry",
                    "expected": "component object",
                    "actual": type(component).__name__,
                }
            )
            continue
        raw_name = component.get("name")
        raw_path = component.get("path")
        raw_expected = component.get("commit") or component.get("ref")
        if not isinstance(raw_path, str) or not isinstance(raw_expected, str):
            blockers.append(
                {
                    "name": raw_name.strip() if isinstance(raw_name, str) and raw_name.strip() else f"components[{index}]",
                    "path": "",
                    "expected": "",
                    "actual": "",
                    "status": "invalid_entry",
                }
            )
            continue
        name = raw_name.strip() if isinstance(raw_name, str) else ""
        rel_path = raw_path.strip()
        expected = raw_expected.strip()
        if not rel_path or not expected:
            blockers.append(
                {
                    "name": name or f"components[{index}]",
                    "path": rel_path if rel_path and safe_component_path(repo, rel_path) is not None else "",
                    "expected": expected if FULL_GIT_SHA_RE.fullmatch(expected) else "",
                    "actual": "",
                    "status": "invalid_entry",
                }
            )
            continue
        component_path = safe_component_path(repo, rel_path)
        if component_path is None:
            blockers.append(
                {
                    "name": name or f"components[{index}]",
                    "path": "<unsafe-path>",
                    "expected": expected if FULL_GIT_SHA_RE.fullmatch(expected) else "<invalid-ref>",
                    "actual": "",
                    "status": "unsafe_path",
                }
            )
            continue
        if not FULL_GIT_SHA_RE.fullmatch(expected):
            blockers.append(
                {
                    "name": name or rel_path,
                    "path": rel_path,
                    "expected": "<invalid-ref>",
                    "actual": "",
                    "status": "invalid_ref",
                }
            )
            continue
        expected = expected.lower()
        expected_origin = component.get("_locked_origin", component.get("origin"))
        if not isinstance(expected_origin, str) or canonical_repository_identity(
            expected_origin,
            base_dir=repo,
        ) is None:
            blockers.append(
                {
                    "name": name or rel_path,
                    "path": rel_path,
                    "expected": expected,
                    "actual": "",
                    "status": "invalid_origin",
                }
            )
            continue
        if not component_path.exists():
            refresh_required.append(
                {
                    "name": name or rel_path,
                    "path": rel_path,
                    "expected": expected,
                    "actual": "",
                    "status": "missing_checkout",
                }
            )
            continue
        if not (component_path / ".git").exists():
            blockers.append(
                {
                    "name": name or rel_path,
                    "path": rel_path,
                    "expected": expected,
                    "actual": "",
                    "status": "unverifiable_checkout",
                }
            )
            continue
        proc = run_git(component_path, "rev-parse", "HEAD")
        actual = proc.stdout.strip().lower() if proc.returncode == 0 else ""
        if actual and not FULL_GIT_SHA_RE.fullmatch(actual):
            actual = ""
        if not actual:
            blockers.append(
                {
                    "name": name or rel_path,
                    "path": rel_path,
                    "expected": expected,
                    "actual": "",
                    "status": "unreadable_head",
                }
            )
            continue
        origin_status = component_origin_status(
            component_path,
            expected_origin,
            expected_base_dir=repo,
        )
        if origin_status is not None:
            blockers.append(
                {
                    "name": name or rel_path,
                    "path": rel_path,
                    "expected": expected,
                    "actual": actual,
                    "status": origin_status,
                }
            )
            continue
        dirty_proc = run_git(component_path, "status", "--porcelain")
        if dirty_proc.returncode != 0:
            blockers.append(
                {
                    "name": name or rel_path,
                    "path": rel_path,
                    "expected": expected,
                    "actual": actual,
                    "status": "unreadable_worktree",
                }
            )
            continue
        if dirty_proc.stdout.strip():
            blockers.append(
                {
                    "name": name or rel_path,
                    "path": rel_path,
                    "expected": expected,
                    "actual": actual,
                    "status": "dirty_worktree",
                }
            )
        elif actual != expected:
            refresh_required.append(
                {
                    "name": name or rel_path,
                    "path": rel_path,
                    "expected": expected,
                    "actual": actual,
                    "status": "head_mismatch",
                }
            )
    return blockers, refresh_required


def _read_expected_digest(path: Path) -> str | None:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value.lower() if SHA256_RE.fullmatch(value) else None


def _is_universal_macos_binary(path: Path) -> bool:
    """Validate that a Mach-O fat binary contains both supported Mac architectures."""
    try:
        with path.open("rb") as handle:
            header = handle.read(8)
            if len(header) != 8:
                return False
            magic_bytes = header[:4]
            if magic_bytes == b"\xca\xfe\xba\xbe":
                byte_order, arch_size = ">", 20
            elif magic_bytes == b"\xbe\xba\xfe\xca":
                byte_order, arch_size = "<", 20
            elif magic_bytes == b"\xca\xfe\xba\xbf":
                byte_order, arch_size = ">", 32
            elif magic_bytes == b"\xbf\xba\xfe\xca":
                byte_order, arch_size = "<", 32
            else:
                return False
            arch_count = struct.unpack(f"{byte_order}I", header[4:])[0]
            if arch_count < 2 or arch_count > 64:
                return False
            architectures: set[int] = set()
            for _ in range(arch_count):
                arch = handle.read(arch_size)
                if len(arch) != arch_size:
                    return False
                architectures.add(struct.unpack(f"{byte_order}I", arch[:4])[0])
    except OSError:
        return False
    cpu_arch_abi64 = 0x01000000
    return {cpu_arch_abi64 | 7, cpu_arch_abi64 | 12}.issubset(architectures)


def helper_needs_rebuild(repo: Path) -> bool:
    helper_dir = repo / HELPER_RELATIVE_PATH
    if not helper_dir.exists():
        return False
    paths = [
        helper_dir / "Package.swift",
        helper_dir / "Sources" / "ViventiumHelper" / "ViventiumHelperApp.swift",
        helper_dir / "Sources" / "ViventiumHelper" / "Resources" / "Info.plist",
    ]
    prebuilt_dir = helper_dir / "prebuilt"
    source_hash_file = prebuilt_dir / "source.sha256"
    binary = prebuilt_dir / HELPER_BINARY_NAME
    binary_hash_file = prebuilt_dir / "binary.sha256"
    if not all(path.is_file() for path in paths):
        return True
    source_hash = _read_expected_digest(source_hash_file)
    binary_hash = _read_expected_digest(binary_hash_file)
    if source_hash is None or binary_hash is None:
        return True
    if not binary.is_file() or not os.access(binary, os.X_OK) or not _is_universal_macos_binary(binary):
        return True

    digest = hashlib.sha256()
    try:
        for path in paths:
            digest.update(path.relative_to(helper_dir).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    except OSError:
        return True
    if digest.hexdigest() != source_hash:
        return True
    try:
        binary_digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    except OSError:
        return True
    return binary_digest != binary_hash


def stack_running(app_support_dir: Path) -> bool:
    state_root = app_support_dir / "state" / "runtime"
    if not state_root.exists():
        return False
    for path in state_root.rglob("detached-launch.pgid"):
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 64:
                continue
            if path.read_text(encoding="utf-8").strip():
                return True
        except (OSError, UnicodeError):
            continue
    return False


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo_root).expanduser().resolve()
    app_support = Path(args.app_support_dir).expanduser().resolve()
    branch = current_branch(repo)
    upstream = ""
    ahead = 0
    behind = 0
    remote_head = ""
    remote_history_complete = True
    fetch_error = ""
    if args.no_fetch:
        upstream_proc = run_git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
        if upstream_proc.returncode == 0:
            upstream_ref = upstream_proc.stdout.strip()
            if upstream_ref:
                upstream = "<configured-upstream>"
                local_ahead = git_line_count(repo, "rev-list", f"{upstream_ref}..HEAD")
                local_behind = git_line_count(repo, "rev-list", f"HEAD..{upstream_ref}")
                if local_ahead is None or local_behind is None:
                    fetch_error = "git_unavailable"
                else:
                    ahead = local_ahead
                    behind = local_behind
    else:
        remote = observe_remote(repo, branch)
        upstream = str(remote["upstream"])
        remote_head = str(remote["remote_head"])
        ahead = int(remote["ahead"])
        behind = int(remote["behind"])
        remote_history_complete = bool(remote["history_complete"])
        fetch_error = str(remote["error"])

    dirty = tracked_dirty(repo)
    config_file = Path(args.config_file).expanduser().resolve() if args.config_file else None
    lock_drift, component_refresh = component_alignment(repo, config_file)
    running = stack_running(app_support)
    helper_rebuild = helper_needs_rebuild(repo)
    blockers: list[str] = []
    if dirty and not args.allow_dirty_parent:
        blockers.append("dirty_checkout")
    if lock_drift:
        blockers.append("component_lock_drift")
    if fetch_error:
        blockers.append("fetch_failed")
    if helper_rebuild:
        blockers.append("helper_rebuild_needed")
    return {
        "schema_version": 1,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": "<repo>",
        "branch": branch,
        "upstream": upstream,
        "update_available": behind > 0 or bool(component_refresh),
        "commits_ahead": ahead,
        "commits_behind": behind,
        "remote_head": remote_head,
        "remote_history_complete": remote_history_complete,
        "dirty_checkout": dirty,
        "stack_running": running,
        "helper_needs_rebuild": helper_rebuild,
        "component_lock_drift": lock_drift,
        "component_refresh_required": component_refresh,
        "fetch_error": fetch_error,
        "blockers": blockers,
        "ready_to_upgrade": not blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--app-support-dir", required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-fetch", action="store_true")
    parser.add_argument("--config-file")
    parser.add_argument("--allow-dirty-parent", action="store_true")
    args = parser.parse_args(argv)
    report = build_report(args)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["blockers"]:
        print(f"Update blocked: {', '.join(report['blockers'])}")
    elif report["update_available"]:
        print(f"Update available: {report['commits_behind']} commit(s) behind {report['upstream']}")
    else:
        print("Viventium is up to date.")
    if report["fetch_error"]:
        return 2
    if report["blockers"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
