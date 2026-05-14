#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def run_git(repo: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git_output(repo: Path, *args: str) -> str:
    return run_git(repo, *args, check=True).stdout.strip()


def current_branch(repo: Path) -> str:
    return git_output(repo, "rev-parse", "--abbrev-ref", "HEAD")


def tracked_dirty(repo: Path) -> bool:
    return bool(git_output(repo, "status", "--porcelain", "--untracked-files=no"))


def count_lines(value: str) -> int:
    return len([line for line in value.splitlines() if line.strip()])


def component_lock_drift(repo: Path) -> list[dict[str, str]]:
    lock_path = repo / "components.lock.json"
    if not lock_path.exists():
        return []
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception:
        return [{"name": "components.lock.json", "status": "invalid", "expected": "", "actual": ""}]
    components = payload.get("components")
    if not isinstance(components, list):
        return []
    drift: list[dict[str, str]] = []
    for component in components:
        if not isinstance(component, dict):
            continue
        name = str(component.get("name") or component.get("path") or "").strip()
        rel_path = str(component.get("path") or "").strip()
        expected = str(component.get("commit") or component.get("ref") or "").strip()
        if not rel_path or not expected:
            continue
        component_path = repo / rel_path
        if not (component_path / ".git").exists():
            continue
        proc = run_git(component_path, "rev-parse", "HEAD")
        actual = proc.stdout.strip() if proc.returncode == 0 else ""
        if actual and actual != expected:
            drift.append(
                {
                    "name": name or rel_path,
                    "path": rel_path,
                    "expected": expected,
                    "actual": actual,
                    "status": "head_mismatch",
                }
            )
    return drift


def helper_needs_rebuild(repo: Path) -> bool:
    helper_dir = repo / "apps/macos/ViventiumHelper"
    paths = [
        helper_dir / "Package.swift",
        helper_dir / "Sources" / "ViventiumHelper" / "ViventiumHelperApp.swift",
        helper_dir / "Sources" / "ViventiumHelper" / "Resources" / "Info.plist",
    ]
    hash_file = helper_dir / "prebuilt/source.sha256"
    if not hash_file.exists() or not all(path.exists() for path in paths):
        return False
    import hashlib

    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(helper_dir).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest() != hash_file.read_text(encoding="utf-8").strip()


def stack_running(app_support_dir: Path) -> bool:
    state_root = app_support_dir / "state" / "runtime"
    if not state_root.exists():
        return False
    return any(path.name == "detached-launch.pgid" and path.read_text(encoding="utf-8").strip() for path in state_root.rglob("*"))


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo_root).expanduser().resolve()
    app_support = Path(args.app_support_dir).expanduser().resolve()
    branch = current_branch(repo)
    fetch_error = ""
    if not args.no_fetch:
        fetch = run_git(repo, "fetch", "origin", branch)
        if fetch.returncode != 0:
            fetch_error = fetch.stderr.strip() or fetch.stdout.strip()

    upstream = ""
    ahead = 0
    behind = 0
    upstream_proc = run_git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if upstream_proc.returncode == 0:
        upstream = upstream_proc.stdout.strip()
        ahead = count_lines(git_output(repo, "rev-list", f"{upstream}..HEAD"))
        behind = count_lines(git_output(repo, "rev-list", f"HEAD..{upstream}"))

    dirty = tracked_dirty(repo)
    lock_drift = component_lock_drift(repo)
    running = stack_running(app_support)
    helper_rebuild = helper_needs_rebuild(repo)
    blockers: list[str] = []
    if dirty:
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
        "repo_root": str(repo),
        "branch": branch,
        "upstream": upstream,
        "update_available": behind > 0,
        "commits_ahead": ahead,
        "commits_behind": behind,
        "dirty_checkout": dirty,
        "stack_running": running,
        "helper_needs_rebuild": helper_rebuild,
        "component_lock_drift": lock_drift,
        "fetch_error": fetch_error,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--app-support-dir", required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-fetch", action="store_true")
    args = parser.parse_args(argv)
    report = build_report(args)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["update_available"]:
        print(f"Update available: {report['commits_behind']} commit(s) behind {report['upstream']}")
    else:
        print("Viventium is up to date.")
    return 0 if not report["fetch_error"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
