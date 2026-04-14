#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_mtime_iso(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except FileNotFoundError:
        return None


def sanitize_path_label(path: Path) -> str:
    try:
        resolved = path.expanduser().resolve()
    except Exception:
        resolved = path.expanduser()
    home = Path.home().resolve()
    if resolved == home:
        return "~"
    try:
        return "~/" + str(resolved.relative_to(home))
    except Exception:
        name = resolved.name or resolved.as_posix().rstrip("/").split("/")[-1]
        return f"<local>/{name}" if name else "<local>"


def parse_timestamp(value: Any) -> datetime | None:
    if value in (None, "", 0):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def load_env_file(path: Path) -> dict[str, str]:
    payload: dict[str, str] = {}
    if not path.is_file():
        return payload
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        try:
            payload[key] = shlex.split(f"ignored={value}", comments=False)[0].split("=", 1)[1]
        except Exception:
            payload[key] = value.strip("'\"")
    return payload


def run_command(args: list[str], *, timeout: int = 10, cwd: Path | None = None) -> str | None:
    try:
        completed = subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return completed.stdout.strip()


def git_head(repo_dir: Path) -> str | None:
    return run_command(["git", "rev-parse", "HEAD"], timeout=5, cwd=repo_dir)


def read_mongo_summary(mongo_uri: str | None) -> tuple[dict[str, Any], list[str]]:
    summary: dict[str, Any] = {
        "available": False,
        "latestMessageCreatedAt": None,
        "savedMemoryCount": None,
        "latestSavedMemoryUpdatedAt": None,
    }
    warnings: list[str] = []
    if not mongo_uri:
        warnings.append("Mongo continuity introspection skipped: missing MONGO_URI.")
        return summary, warnings
    if not shutil_which("mongosh"):
        warnings.append("Mongo continuity introspection skipped: mongosh not found.")
        return summary, warnings

    script = r"""
const collections = new Set(db.getCollectionNames());
function latestIso(collectionName, fieldName) {
  if (!collections.has(collectionName)) {
    return null;
  }
  const sort = {};
  sort[fieldName] = -1;
  const doc = db.getCollection(collectionName).find({}).sort(sort).limit(1).next();
  if (!doc || !doc[fieldName]) {
    return null;
  }
  try {
    return new Date(doc[fieldName]).toISOString();
  } catch (_error) {
    return null;
  }
}
function countDocs(collectionName) {
  if (!collections.has(collectionName)) {
    return null;
  }
  return db.getCollection(collectionName).countDocuments({});
}
print(JSON.stringify({
  latestMessageCreatedAt: latestIso("messages", "createdAt"),
  savedMemoryCount: countDocs("memoryentries"),
  latestSavedMemoryUpdatedAt: latestIso("memoryentries", "updatedAt"),
}));
"""
    raw = run_command(["mongosh", mongo_uri, "--quiet", "--eval", script], timeout=12)
    if raw is None:
        warnings.append("Mongo continuity introspection failed: mongosh query did not return JSON.")
        return summary, warnings
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        warnings.append("Mongo continuity introspection failed: invalid JSON payload from mongosh.")
        return summary, warnings
    summary.update(
        {
            "available": True,
            "latestMessageCreatedAt": payload.get("latestMessageCreatedAt"),
            "savedMemoryCount": payload.get("savedMemoryCount"),
            "latestSavedMemoryUpdatedAt": payload.get("latestSavedMemoryUpdatedAt"),
        }
    )
    return summary, warnings


def read_schedule_summary(db_path: Path) -> tuple[dict[str, Any], list[str]]:
    summary: dict[str, Any] = {
        "dbPresent": db_path.is_file(),
        "activeCount": None,
        "latestUpdatedAt": None,
    }
    warnings: list[str] = []
    if not db_path.is_file():
        return summary, warnings
    try:
        connection = sqlite3.connect(str(db_path))
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        active_count = cursor.execute(
            "SELECT COUNT(*) AS count FROM scheduled_tasks WHERE active = 1"
        ).fetchone()
        latest_updated = cursor.execute(
            "SELECT updated_at FROM scheduled_tasks ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        summary["activeCount"] = int(active_count["count"]) if active_count else 0
        summary["latestUpdatedAt"] = latest_updated["updated_at"] if latest_updated else None
    except sqlite3.DatabaseError as exc:
        warnings.append(f"Schedule continuity introspection failed: {exc}.")
    finally:
        try:
            connection.close()  # type: ignore[name-defined]
        except Exception:
            pass
    return summary, warnings


def relative_label(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return path.name


def shutil_which(command: str) -> str | None:
    return run_command(["/usr/bin/which", command], timeout=2) or None


def default_runtime_profile(runtime_env: dict[str, str]) -> str:
    return (
        runtime_env.get("VIVENTIUM_RUNTIME_PROFILE")
        or os.environ.get("VIVENTIUM_RUNTIME_PROFILE")
        or "isolated"
    )


def recall_marker_path(app_support_dir: Path, runtime_profile: str, runtime_env: dict[str, str]) -> Path:
    env_override = runtime_env.get("VIVENTIUM_RECALL_REBUILD_REQUIRED_FILE") or os.environ.get(
        "VIVENTIUM_RECALL_REBUILD_REQUIRED_FILE"
    )
    if env_override:
        return Path(env_override).expanduser()
    return app_support_dir / "state" / "runtime" / runtime_profile / "continuity" / "recall-rebuild-required.json"


def capture_manifest(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(args.repo_root).resolve()
    app_support_dir = Path(args.app_support_dir).expanduser().resolve()
    config_file = Path(args.config_file or app_support_dir / "config.yaml").expanduser().resolve()
    runtime_dir = Path(args.runtime_dir or app_support_dir / "runtime").expanduser().resolve()
    runtime_env_path = runtime_dir / "runtime.env"
    runtime_env = load_env_file(runtime_env_path)
    runtime_profile = default_runtime_profile(runtime_env)
    state_root = app_support_dir / "state" / "runtime" / runtime_profile
    recall_marker = recall_marker_path(app_support_dir, runtime_profile, runtime_env)
    scheduling_db = Path(
        runtime_env.get("SCHEDULING_DB_PATH") or state_root / "scheduling" / "schedules.db"
    ).expanduser()

    mongo_summary, mongo_warnings = read_mongo_summary(runtime_env.get("MONGO_URI"))
    schedule_summary, schedule_warnings = read_schedule_summary(scheduling_db)

    warnings: list[str] = []
    errors: list[str] = []
    warnings.extend(mongo_warnings)
    warnings.extend(schedule_warnings)

    if recall_marker.exists():
        errors.append(
            "Conversation recall rebuild is still required for this runtime profile before vector-backed recall is trustworthy."
        )

    manifest: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "capturedAt": iso_now(),
        "label": args.label or "continuity-audit",
        "paths": {
            "appSupportDir": sanitize_path_label(app_support_dir),
            "configFile": relative_label(config_file, app_support_dir),
            "runtimeEnv": relative_label(runtime_env_path, app_support_dir),
            "stateRoot": relative_label(state_root, app_support_dir),
            "schedulingDb": relative_label(scheduling_db, app_support_dir),
            "recallRebuildMarker": relative_label(recall_marker, app_support_dir),
        },
        "repo": {
            "parentHead": git_head(repo_root),
            "librechatHead": git_head(repo_root / "viventium_v0_4" / "LibreChat"),
        },
        "runtime": {
            "profile": runtime_profile,
            "defaultConversationRecall": runtime_env.get("VIVENTIUM_DEFAULT_CONVERSATION_RECALL"),
            "embeddingsProvider": runtime_env.get("VIVENTIUM_RAG_EMBEDDINGS_PROVIDER"),
            "embeddingsModel": runtime_env.get("VIVENTIUM_RAG_EMBEDDINGS_MODEL"),
            "embeddingsProfile": runtime_env.get("VIVENTIUM_RAG_EMBEDDINGS_PROFILE"),
        },
        "files": {
            "configUpdatedAt": file_mtime_iso(config_file),
            "runtimeEnvUpdatedAt": file_mtime_iso(runtime_env_path),
            "schedulingDbUpdatedAt": file_mtime_iso(scheduling_db),
            "recallMarkerUpdatedAt": file_mtime_iso(recall_marker),
        },
        "surfaces": {
            "messages": {
                "latestTimestamp": mongo_summary.get("latestMessageCreatedAt"),
                "available": bool(mongo_summary.get("available")),
            },
            "savedMemory": {
                "latestTimestamp": mongo_summary.get("latestSavedMemoryUpdatedAt"),
                "count": mongo_summary.get("savedMemoryCount"),
                "available": bool(mongo_summary.get("available")),
            },
            "schedules": {
                "latestTimestamp": schedule_summary.get("latestUpdatedAt"),
                "activeCount": schedule_summary.get("activeCount"),
                "dbPresent": schedule_summary.get("dbPresent"),
            },
            "recall": {
                "rebuildRequired": recall_marker.exists(),
            },
        },
        "warnings": warnings,
        "errors": errors,
    }
    manifest["status"] = (
        "error" if manifest["errors"] else "warning" if manifest["warnings"] else "ok"
    )
    return manifest


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def compare_manifests(args: argparse.Namespace) -> dict[str, Any]:
    snapshot_manifest = load_manifest(Path(args.snapshot_manifest))
    live_manifest = load_manifest(Path(args.live_manifest))
    warnings: list[str] = []
    errors: list[str] = []
    surfaces: dict[str, Any] = {}

    snapshot_schema = snapshot_manifest.get("schemaVersion")
    live_schema = live_manifest.get("schemaVersion")
    if snapshot_schema != live_schema:
        warnings.append(
            "Snapshot and live continuity manifests use different schema versions; comparison may be partial."
        )

    metadata_differences: list[dict[str, Any]] = []
    runtime_keys = (
        "profile",
        "defaultConversationRecall",
        "embeddingsProvider",
        "embeddingsModel",
        "embeddingsProfile",
    )
    snapshot_runtime = snapshot_manifest.get("runtime") or {}
    live_runtime = live_manifest.get("runtime") or {}
    for key in runtime_keys:
        snapshot_value = snapshot_runtime.get(key)
        live_value = live_runtime.get(key)
        if snapshot_value != live_value:
            metadata_differences.append(
                {
                    "field": f"runtime.{key}",
                    "snapshotValue": snapshot_value,
                    "liveValue": live_value,
                }
            )

    snapshot_recall = ((snapshot_manifest.get("surfaces") or {}).get("recall") or {}).get(
        "rebuildRequired"
    )
    live_recall = ((live_manifest.get("surfaces") or {}).get("recall") or {}).get("rebuildRequired")
    if snapshot_recall != live_recall:
        metadata_differences.append(
            {
                "field": "surfaces.recall.rebuildRequired",
                "snapshotValue": snapshot_recall,
                "liveValue": live_recall,
            }
        )
    if metadata_differences:
        warnings.append(
            "Snapshot continuity metadata differs from live runtime state; review runtime/recall settings before trusting the restore."
        )

    comparable_surfaces = ("messages", "savedMemory", "schedules")
    older_surfaces: list[str] = []

    for surface_name in comparable_surfaces:
        snapshot_surface = (snapshot_manifest.get("surfaces") or {}).get(surface_name) or {}
        live_surface = (live_manifest.get("surfaces") or {}).get(surface_name) or {}
        snapshot_ts = parse_timestamp(snapshot_surface.get("latestTimestamp"))
        live_ts = parse_timestamp(live_surface.get("latestTimestamp"))
        relation = "unknown"
        if snapshot_ts and live_ts:
            if snapshot_ts < live_ts:
                relation = "older"
                older_surfaces.append(surface_name)
            elif snapshot_ts > live_ts:
                relation = "newer"
            else:
                relation = "equal"
        elif live_ts and not snapshot_ts:
            warnings.append(
                f"Snapshot continuity surface `{surface_name}` is missing a comparable timestamp while live state has one."
            )
        elif snapshot_ts and not live_ts:
            warnings.append(
                f"Live continuity surface `{surface_name}` is missing a comparable timestamp while the snapshot has one."
            )
        surfaces[surface_name] = {
            "snapshotTimestamp": snapshot_surface.get("latestTimestamp"),
            "liveTimestamp": live_surface.get("latestTimestamp"),
            "relation": relation,
        }

    if older_surfaces:
        errors.append(
            "Snapshot continuity state is older than current live state for: "
            + ", ".join(sorted(older_surfaces))
            + "."
        )
    if not older_surfaces and all(
        surfaces[surface_name]["relation"] == "unknown" for surface_name in comparable_surfaces
    ):
        warnings.append(
            "No continuity surfaces exposed comparable timestamps; restore age could not be proven."
        )

    result = {
        "schemaVersion": SCHEMA_VERSION,
        "comparedAt": iso_now(),
        "snapshotManifest": sanitize_path_label(Path(args.snapshot_manifest)),
        "liveManifest": sanitize_path_label(Path(args.live_manifest)),
        "surfaces": surfaces,
        "metadataDifferences": metadata_differences,
        "olderSurfaces": older_surfaces,
        "warnings": warnings,
        "errors": errors,
    }
    result["status"] = "error" if errors else "warning" if warnings else "ok"
    return result


def emit_json(payload: dict[str, Any], output_path: str | None) -> int:
    rendered = json.dumps(payload, indent=2) + "\n"
    if output_path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture and compare continuity metadata.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser("capture", help="Capture continuity metadata for the current install.")
    capture.add_argument("--repo-root", required=True)
    capture.add_argument("--app-support-dir", required=True)
    capture.add_argument("--config-file")
    capture.add_argument("--runtime-dir")
    capture.add_argument("--label")
    capture.add_argument("--output")

    compare = subparsers.add_parser("compare", help="Compare a snapshot manifest against live continuity metadata.")
    compare.add_argument("--snapshot-manifest", required=True)
    compare.add_argument("--live-manifest", required=True)
    compare.add_argument("--output")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "capture":
        return emit_json(capture_manifest(args), args.output)
    if args.command == "compare":
        return emit_json(compare_manifests(args), args.output)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
