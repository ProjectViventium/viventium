#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import sqlite3
import stat
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 2
MAX_UPLOAD_FILE_BYTES = 64 * 1024 * 1024 * 1024
MAX_UPLOAD_TOTAL_BYTES = 256 * 1024 * 1024 * 1024
MAX_UPLOAD_FILES = 100_000
MAX_UPLOAD_ENTRIES = 200_000
MAX_UPLOAD_PATH_BYTES = 1024
MAX_UPLOAD_PATH_DEPTH = 32


def preserved_other_runtime_uploads_link_is_receipted(
    *,
    legacy: Path,
    app_support_dir: Path,
) -> bool:
    try:
        raw_target = Path(os.readlink(legacy))
        if not raw_target.is_absolute():
            return False
        target = raw_target
        target = Path(os.path.abspath(os.path.expanduser(str(target))))
        receipt = (
            app_support_dir
            / "state"
            / "continuity"
            / "uploads-migration"
            / "receipt.json"
        )
        for directory in (
            app_support_dir,
            receipt.parent.parent.parent,
            receipt.parent.parent,
            receipt.parent,
        ):
            metadata = directory.lstat()
            if (
                stat.S_ISLNK(metadata.st_mode)
                or not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_uid != os.getuid()
            ):
                return False
        metadata = receipt.lstat()
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or metadata.st_mode & 0o077
        ):
            return False
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        return (
            isinstance(payload, dict)
            and payload.get("schemaVersion") == 1
            and payload.get("legacyCompatibility")
            == "other_runtime_exact_symlink_preserved"
            and payload.get("mode") == "isolated_runtime_root"
            and payload.get("observedLinkTargetSha256")
            == hashlib.sha256(os.fsencode(str(target))).hexdigest()
            and payload.get("canonicalStorage") == "app_support_data_uploads"
        )
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return False


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


def read_uploads_semantic_fingerprint(path: Path) -> tuple[dict[str, Any], list[str]]:
    """Fingerprint upload meaning without publishing names, paths, or content."""

    unavailable = {
        "available": False,
        "fileCount": None,
        "totalBytes": None,
        "treeSha256": None,
    }
    warnings: list[str] = []
    root = Path(os.path.abspath(os.path.expanduser(str(path))))
    try:
        root_metadata = root.lstat()
    except FileNotFoundError:
        return {
            "available": True,
            "fileCount": 0,
            "totalBytes": 0,
            "treeSha256": hashlib.sha256().hexdigest(),
        }, warnings
    except OSError:
        warnings.append("Uploads semantic fingerprint failed: root metadata is unavailable.")
        return unavailable, warnings
    if (
        stat.S_ISLNK(root_metadata.st_mode)
        or not stat.S_ISDIR(root_metadata.st_mode)
        or root_metadata.st_uid != os.getuid()
    ):
        warnings.append(
            "Uploads semantic fingerprint failed: root type or ownership is unsafe."
        )
        return unavailable, warnings

    digest = hashlib.sha256()
    file_count = 0
    entry_count = 0
    total_bytes = 0
    pending: list[tuple[Path, Path]] = [(root, Path("."))]
    try:
        while pending:
            directory, relative_directory = pending.pop()
            directory_metadata = directory.lstat()
            if (
                stat.S_ISLNK(directory_metadata.st_mode)
                or not stat.S_ISDIR(directory_metadata.st_mode)
                or directory_metadata.st_uid != os.getuid()
            ):
                raise ValueError("unsafe directory")
            if relative_directory != Path("."):
                encoded_directory = os.fsencode(str(relative_directory))
                if (
                    len(encoded_directory) > MAX_UPLOAD_PATH_BYTES
                    or len(relative_directory.parts) > MAX_UPLOAD_PATH_DEPTH
                ):
                    raise ValueError("directory bound")
                digest.update(b"D\0")
                digest.update(len(encoded_directory).to_bytes(4, "big"))
                digest.update(encoded_directory)
            entries = sorted(
                os.scandir(directory),
                key=lambda entry: os.fsencode(entry.name),
            )
            child_directories: list[tuple[Path, Path]] = []
            for entry in entries:
                entry_count += 1
                if entry_count > MAX_UPLOAD_ENTRIES:
                    raise ValueError("entry bound")
                relative = (
                    Path(entry.name)
                    if relative_directory == Path(".")
                    else relative_directory / entry.name
                )
                encoded = os.fsencode(str(relative))
                if (
                    len(encoded) > MAX_UPLOAD_PATH_BYTES
                    or len(relative.parts) > MAX_UPLOAD_PATH_DEPTH
                ):
                    raise ValueError("path bound")
                metadata = entry.stat(follow_symlinks=False)
                if metadata.st_uid != os.getuid() or stat.S_ISLNK(metadata.st_mode):
                    raise ValueError("unsafe entry")
                if stat.S_ISDIR(metadata.st_mode):
                    child_directories.append((Path(entry.path), relative))
                    continue
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                    raise ValueError("unsafe file")
                file_count += 1
                total_bytes += metadata.st_size
                if (
                    file_count > MAX_UPLOAD_FILES
                    or metadata.st_size > MAX_UPLOAD_FILE_BYTES
                    or total_bytes > MAX_UPLOAD_TOTAL_BYTES
                ):
                    raise ValueError("file bound")
                flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                descriptor = os.open(entry.path, flags)
                try:
                    opened = os.fstat(descriptor)
                    identity = (
                        metadata.st_dev,
                        metadata.st_ino,
                        metadata.st_size,
                        metadata.st_mtime_ns,
                        metadata.st_ctime_ns,
                    )
                    if (
                        not stat.S_ISREG(opened.st_mode)
                        or opened.st_nlink != 1
                        or identity
                        != (
                            opened.st_dev,
                            opened.st_ino,
                            opened.st_size,
                            opened.st_mtime_ns,
                            opened.st_ctime_ns,
                        )
                    ):
                        raise ValueError("file changed")
                    content_digest = hashlib.sha256()
                    while True:
                        chunk = os.read(descriptor, 1024 * 1024)
                        if not chunk:
                            break
                        content_digest.update(chunk)
                    after = os.fstat(descriptor)
                    if identity != (
                        after.st_dev,
                        after.st_ino,
                        after.st_size,
                        after.st_mtime_ns,
                        after.st_ctime_ns,
                    ):
                        raise ValueError("file changed")
                finally:
                    os.close(descriptor)
                digest.update(b"F\0")
                digest.update(len(encoded).to_bytes(4, "big"))
                digest.update(encoded)
                digest.update(metadata.st_size.to_bytes(8, "big"))
                digest.update(content_digest.digest())
            pending.extend(reversed(child_directories))
    except (OSError, ValueError):
        warnings.append(
            "Uploads semantic fingerprint failed: tree safety, stability, or bounds could not be proven."
        )
        return unavailable, warnings

    return {
        "available": True,
        "fileCount": file_count,
        "totalBytes": total_bytes,
        "treeSha256": digest.hexdigest(),
    }, warnings


def resolve_uploads_audit_root(
    *,
    repo_root: Path,
    app_support_dir: Path,
    runtime_env: dict[str, str],
) -> tuple[Path | None, list[str]]:
    """Resolve canonical vs predecessor storage without hiding an ambiguous split."""

    canonical = app_support_dir / "data" / "uploads"
    legacy = repo_root / "viventium_v0_4" / "LibreChat" / "uploads"
    configured = runtime_env.get("VIVENTIUM_LIBRECHAT_UPLOADS_ROOT")
    if configured and Path(os.path.abspath(os.path.expanduser(configured))) != canonical:
        return None, [
            "Uploads semantic fingerprint failed: generated canonical root is outside App Support."
        ]

    try:
        legacy_metadata = legacy.lstat()
    except FileNotFoundError:
        legacy_metadata = None
    except OSError:
        return None, ["Uploads semantic fingerprint failed: predecessor root is unavailable."]
    try:
        canonical_metadata = canonical.lstat()
    except FileNotFoundError:
        canonical_metadata = None
    except OSError:
        return None, ["Uploads semantic fingerprint failed: canonical root is unavailable."]

    if legacy_metadata is not None and stat.S_ISLNK(legacy_metadata.st_mode):
        try:
            link_target = Path(os.readlink(legacy))
        except OSError:
            return None, [
                "Uploads semantic fingerprint failed: predecessor link is unreadable."
            ]
        if link_target.is_absolute() and Path(os.path.abspath(str(link_target))) == canonical:
            return canonical, []
        if (
            canonical_metadata is not None
            and stat.S_ISDIR(canonical_metadata.st_mode)
            and canonical_metadata.st_uid == os.getuid()
            and preserved_other_runtime_uploads_link_is_receipted(
                legacy=legacy,
                app_support_dir=app_support_dir,
            )
        ):
            return canonical, []
        return None, [
            "Uploads semantic fingerprint failed: predecessor root is an unexpected symlink."
        ]

    # A pre-upgrade manifest produced by the predecessor runtime has no
    # canonical variable yet, so its checkout tree remains authoritative.
    if not configured:
        return legacy, []

    if canonical_metadata is None:
        return legacy, []
    if legacy_metadata is None:
        return canonical, []
    if not stat.S_ISDIR(canonical_metadata.st_mode) or not stat.S_ISDIR(
        legacy_metadata.st_mode
    ):
        return None, [
            "Uploads semantic fingerprint failed: canonical/predecessor root type is unsafe."
        ]
    try:
        with os.scandir(canonical) as entries:
            canonical_has_entries = next(entries, None) is not None
        with os.scandir(legacy) as entries:
            legacy_has_entries = next(entries, None) is not None
    except OSError:
        return None, [
            "Uploads semantic fingerprint failed: canonical/predecessor trees cannot be compared."
        ]
    if canonical_has_entries and legacy_has_entries:
        return None, [
            "Uploads semantic fingerprint failed: canonical and predecessor trees are both populated."
        ]
    if legacy_has_entries:
        return legacy, []
    return canonical, []


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


def read_mongo_semantic_fingerprint(
    mongo_uri: str | None,
    repo_root: Path,
) -> tuple[dict[str, Any], list[str]]:
    summary: dict[str, Any] = {
        "available": False,
        "collections": {},
    }
    warnings: list[str] = []
    if not mongo_uri:
        warnings.append("Mongo semantic fingerprint skipped: missing MONGO_URI.")
        return summary, warnings
    node_bin = shutil_which("node")
    adapter = repo_root / "scripts" / "viventium" / "continuity_mongo.cjs"
    if not node_bin or not adapter.is_file():
        warnings.append("Mongo semantic fingerprint skipped: local adapter prerequisites are missing.")
        return summary, warnings
    raw = run_command(
        [
            node_bin,
            str(adapter),
            "fingerprint",
            "--repo-root",
            str(repo_root),
            "--uri",
            mongo_uri,
        ],
        timeout=30,
    )
    if raw is None:
        warnings.append("Mongo semantic fingerprint failed: local adapter did not return metadata.")
        return summary, warnings
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        warnings.append("Mongo semantic fingerprint failed: local adapter returned invalid metadata.")
        return summary, warnings
    collections = payload.get("collections")
    if payload.get("ok") is not True or not isinstance(collections, dict):
        warnings.append("Mongo semantic fingerprint failed: local adapter result was incomplete.")
        return summary, warnings
    summary["available"] = True
    summary["collections"] = collections
    return summary, warnings


def read_config_semantic_fingerprint(config_path: Path) -> tuple[dict[str, Any], list[str]]:
    summary: dict[str, Any] = {
        "available": False,
        "leafCount": None,
        "leafDigests": [],
    }
    warnings: list[str] = []
    if not config_path.is_file():
        warnings.append("Canonical config semantic fingerprint skipped: config file is missing.")
        return summary, warnings
    try:
        import yaml
    except ImportError:
        warnings.append("Canonical config semantic fingerprint skipped: YAML parser is unavailable.")
        return summary, warnings
    try:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        warnings.append("Canonical config semantic fingerprint failed: config is unreadable.")
        return summary, warnings

    digests: list[str] = []

    def visit(value: Any, path: tuple[str, ...]) -> None:
        if isinstance(value, dict):
            for key in sorted(value, key=lambda item: str(item)):
                visit(value[key], (*path, str(key)))
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, (*path, str(index)))
            return
        encoded = json.dumps(
            {
                "path": path,
                "type": type(value).__name__,
                "value": value,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        digests.append(hashlib.sha256(encoded).hexdigest())

    visit(payload, ())
    summary["available"] = True
    summary["leafCount"] = len(digests)
    summary["leafDigests"] = sorted(digests)
    return summary, warnings


def resolve_mongo_uri(runtime_env: dict[str, str], runtime_dir: Path) -> str | None:
    mongo_uri = runtime_env.get("MONGO_URI")
    if mongo_uri:
        return mongo_uri

    librechat_env = runtime_dir / "service-env" / "librechat.env"
    if librechat_env.is_file():
        service_env = load_env_file(librechat_env)
        mongo_uri = service_env.get("MONGO_URI")
        if mongo_uri:
            return mongo_uri

    mongo_port = runtime_env.get("VIVENTIUM_LOCAL_MONGO_PORT")
    mongo_db = runtime_env.get("VIVENTIUM_LOCAL_MONGO_DB")
    if mongo_port and mongo_db:
        return f"mongodb://127.0.0.1:{mongo_port}/{mongo_db}"

    return None


def read_schedule_summary(db_path: Path) -> tuple[dict[str, Any], list[str]]:
    summary: dict[str, Any] = {
        "dbPresent": db_path.is_file(),
        "available": False,
        "activeCount": None,
        "latestUpdatedAt": None,
        "configurationCount": None,
        "configurationSha256": None,
        "configurationTables": {},
    }
    warnings: list[str] = []
    if not db_path.is_file():
        return summary, warnings
    try:
        connection = sqlite3.connect(str(db_path))
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        present_tables = {
            str(row["name"])
            for row in cursor.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        if "scheduled_tasks" not in present_tables:
            raise sqlite3.DatabaseError("scheduled_tasks table is missing")

        task_columns = {
            str(row["name"])
            for row in cursor.execute("PRAGMA table_info(scheduled_tasks)").fetchall()
        }
        if "active" in task_columns:
            active_count = cursor.execute(
                "SELECT COUNT(*) AS count FROM scheduled_tasks WHERE active = 1"
            ).fetchone()
            summary["activeCount"] = int(active_count["count"]) if active_count else 0
        if "updated_at" in task_columns:
            latest_updated = cursor.execute(
                "SELECT updated_at FROM scheduled_tasks ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
            summary["latestUpdatedAt"] = latest_updated["updated_at"] if latest_updated else None

        semantic_hash = hashlib.sha256()
        configuration_count = 0
        table_counts: dict[str, int] = {}
        protected_tables = sorted(
            table_name
            for table_name in present_tables
            if not table_name.startswith("sqlite_")
        )
        for table_name in protected_tables:
            table_info = cursor.execute(
                f'PRAGMA table_info("{table_name}")'
            ).fetchall()
            selected_columns = [str(row["name"]) for row in table_info]
            if not selected_columns:
                continue
            quoted_columns = ", ".join(f'"{name}"' for name in selected_columns)
            rows = cursor.execute(
                f'SELECT {quoted_columns} FROM "{table_name}"'
            ).fetchall()
            table_counts[table_name] = len(rows)
            configuration_count += len(rows)
            semantic_hash.update(
                json.dumps(
                    {"table": table_name, "columns": selected_columns},
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            semantic_hash.update(b"\n")
            canonical_rows: list[bytes] = []
            for row in rows:
                values: list[Any] = []
                for name in selected_columns:
                    value = row[name]
                    if isinstance(value, bytes):
                        values.append(
                            {
                                "$binaryBytes": len(value),
                                "$binarySha256": hashlib.sha256(value).hexdigest(),
                            }
                        )
                    else:
                        values.append(value)
                canonical_rows.append(
                    json.dumps(
                        values,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ).encode("utf-8")
                )
            for canonical_row in sorted(canonical_rows):
                semantic_hash.update(canonical_row)
                semantic_hash.update(b"\n")
        summary["available"] = True
        summary["configurationCount"] = configuration_count
        summary["configurationSha256"] = semantic_hash.hexdigest()
        summary["configurationTables"] = table_counts
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

    mongo_uri = resolve_mongo_uri(runtime_env, runtime_dir)
    mongo_summary, mongo_warnings = read_mongo_summary(mongo_uri)
    mongo_semantic, mongo_semantic_warnings = read_mongo_semantic_fingerprint(
        mongo_uri,
        repo_root,
    )
    config_semantic, config_semantic_warnings = read_config_semantic_fingerprint(config_file)
    schedule_summary, schedule_warnings = read_schedule_summary(scheduling_db)
    uploads_root, uploads_root_warnings = resolve_uploads_audit_root(
        repo_root=repo_root,
        app_support_dir=app_support_dir,
        runtime_env=runtime_env,
    )
    if uploads_root is None:
        uploads_semantic = {
            "available": False,
            "fileCount": None,
            "totalBytes": None,
            "treeSha256": None,
        }
        uploads_semantic_warnings = uploads_root_warnings
    else:
        uploads_semantic, uploads_semantic_warnings = read_uploads_semantic_fingerprint(
            uploads_root
        )
        uploads_semantic_warnings = uploads_root_warnings + uploads_semantic_warnings

    warnings: list[str] = []
    errors: list[str] = []
    warnings.extend(mongo_warnings)
    warnings.extend(mongo_semantic_warnings)
    warnings.extend(config_semantic_warnings)
    warnings.extend(schedule_warnings)
    warnings.extend(uploads_semantic_warnings)

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
        "semantic": {
            "config": config_semantic,
            "mongo": mongo_semantic,
            "schedules": {
                "available": bool(schedule_summary.get("available")),
                "configurationCount": schedule_summary.get("configurationCount"),
                "configurationSha256": schedule_summary.get("configurationSha256"),
                "configurationTables": schedule_summary.get("configurationTables"),
            },
            "uploads": uploads_semantic,
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
    strict_semantic = bool(getattr(args, "strict_semantic", False))
    if not strict_semantic and not older_surfaces and all(
        surfaces[surface_name]["relation"] == "unknown" for surface_name in comparable_surfaces
    ):
        warnings.append(
            "No continuity surfaces exposed comparable timestamps; restore age could not be proven."
        )

    snapshot_semantic = snapshot_manifest.get("semantic")
    live_semantic = live_manifest.get("semantic")
    semantic_differences: list[dict[str, Any]] = []

    def compare_semantic_values(field: str, snapshot_value: Any, live_value: Any) -> None:
        if isinstance(snapshot_value, dict) and isinstance(live_value, dict):
            for key in sorted(set(snapshot_value) | set(live_value)):
                compare_semantic_values(
                    f"{field}.{key}",
                    snapshot_value.get(key),
                    live_value.get(key),
                )
            return
        if snapshot_value != live_value:
            semantic_differences.append(
                {
                    "field": field,
                    "snapshotValue": snapshot_value,
                    "liveValue": live_value,
                }
            )

    semantic_unavailable: list[str] = []
    if not isinstance(snapshot_semantic, dict) or not isinstance(live_semantic, dict):
        if strict_semantic or snapshot_semantic is not None or live_semantic is not None:
            semantic_unavailable.append("semantic ledger")
    else:
        for domain in ("config", "mongo", "schedules"):
            snapshot_domain = snapshot_semantic.get(domain)
            live_domain = live_semantic.get(domain)
            if domain == "schedules":
                snapshot_schedule_surface = (
                    (snapshot_manifest.get("surfaces") or {}).get("schedules") or {}
                )
                live_schedule_surface = (
                    (live_manifest.get("surfaces") or {}).get("schedules") or {}
                )
                if (
                    isinstance(snapshot_domain, dict)
                    and isinstance(live_domain, dict)
                    and snapshot_domain.get("available") is False
                    and live_domain.get("available") is False
                    and snapshot_schedule_surface.get("dbPresent") is False
                    and live_schedule_surface.get("dbPresent") is False
                ):
                    continue
            if (
                not isinstance(snapshot_domain, dict)
                or not isinstance(live_domain, dict)
                or snapshot_domain.get("available") is not True
                or live_domain.get("available") is not True
            ):
                semantic_unavailable.append(domain)
        if "uploads" in snapshot_semantic or "uploads" in live_semantic:
            snapshot_uploads = snapshot_semantic.get("uploads")
            live_uploads = live_semantic.get("uploads")
            if (
                not isinstance(snapshot_uploads, dict)
                or not isinstance(live_uploads, dict)
                or snapshot_uploads.get("available") is not True
                or live_uploads.get("available") is not True
            ):
                semantic_unavailable.append("uploads")

        snapshot_for_generic = dict(snapshot_semantic)
        live_for_generic = dict(live_semantic)
        snapshot_config = snapshot_for_generic.pop("config", None)
        live_config = live_for_generic.pop("config", None)
        if isinstance(snapshot_config, dict) and isinstance(live_config, dict):
            snapshot_leaves = snapshot_config.get("leafDigests")
            live_leaves = live_config.get("leafDigests")
            if isinstance(snapshot_leaves, list) and isinstance(live_leaves, list):
                missing_leaves = set(snapshot_leaves) - set(live_leaves)
                if missing_leaves:
                    semantic_differences.append(
                        {
                            "field": "semantic.config.protectedLeaves",
                            "snapshotValue": len(snapshot_leaves),
                            "liveValue": len(snapshot_leaves) - len(missing_leaves),
                        }
                    )

        snapshot_mongo = snapshot_for_generic.get("mongo")
        live_mongo = live_for_generic.get("mongo")
        if isinstance(snapshot_mongo, dict) and isinstance(live_mongo, dict):
            snapshot_mongo = dict(snapshot_mongo)
            live_mongo = dict(live_mongo)
            snapshot_collections = dict(snapshot_mongo.get("collections") or {})
            live_collections = dict(live_mongo.get("collections") or {})
            ttl_collection_names = {
                name
                for name in set(snapshot_collections) | set(live_collections)
                if isinstance(snapshot_collections.get(name), dict)
                and "ttl" in snapshot_collections[name]
                or isinstance(live_collections.get(name), dict)
                and "ttl" in live_collections[name]
            }
            live_captured_at = parse_timestamp(live_manifest.get("capturedAt"))
            cutoff_unix_ms = (
                int(live_captured_at.timestamp() * 1000)
                if live_captured_at is not None
                else None
            )

            def protected_ttl_documents(
                collection: Any,
            ) -> tuple[Counter[str] | None, dict[str, Any] | None]:
                if not isinstance(collection, dict) or cutoff_unix_ms is None:
                    return None, None
                ttl = collection.get("ttl")
                if not isinstance(ttl, dict):
                    return None, None
                field = ttl.get("field")
                expire_after_seconds = ttl.get("expireAfterSeconds")
                documents = ttl.get("documents")
                non_expiring = ttl.get("nonExpiring")
                if (
                    not isinstance(field, str)
                    or not field
                    or not isinstance(expire_after_seconds, int)
                    or isinstance(expire_after_seconds, bool)
                    or expire_after_seconds < 0
                    or not isinstance(documents, list)
                    or not isinstance(non_expiring, dict)
                ):
                    return None, None
                non_expiring_count = non_expiring.get("count")
                non_expiring_digest = non_expiring.get("sha256")
                if (
                    not isinstance(non_expiring_count, int)
                    or isinstance(non_expiring_count, bool)
                    or non_expiring_count < 0
                    or not isinstance(non_expiring_digest, str)
                    or len(non_expiring_digest) != 64
                    or any(
                        character not in "0123456789abcdef"
                        for character in non_expiring_digest
                    )
                    or collection.get("count")
                    != len(documents) + non_expiring_count
                ):
                    return None, None
                protected: Counter[str] = Counter()
                if non_expiring_count:
                    protected[f"non-expiring:{non_expiring_digest}"] = (
                        non_expiring_count
                    )
                for document in documents:
                    if not isinstance(document, dict):
                        return None, None
                    digest = document.get("sha256")
                    expiry = document.get("effectiveExpiryUnixMs")
                    if (
                        not isinstance(digest, str)
                        or len(digest) != 64
                        or any(character not in "0123456789abcdef" for character in digest)
                        or (
                            expiry is not None
                            and (
                                not isinstance(expiry, int)
                                or isinstance(expiry, bool)
                            )
                        )
                    ):
                        return None, None
                    if expiry is None:
                        return None, None
                    if expiry > cutoff_unix_ms:
                        protected[f"expiring:{digest}"] += 1
                return protected, {
                    "field": field,
                    "expireAfterSeconds": expire_after_seconds,
                }

            for collection_name in sorted(ttl_collection_names):
                snapshot_collection = snapshot_collections.pop(collection_name, None)
                live_collection = live_collections.pop(collection_name, None)
                snapshot_protected, snapshot_policy = protected_ttl_documents(
                    snapshot_collection
                )
                live_protected, live_policy = protected_ttl_documents(live_collection)
                if snapshot_protected is None or live_protected is None:
                    semantic_unavailable.append(
                        f"mongo TTL lifecycle ledger ({collection_name})"
                    )
                    continue
                if snapshot_policy != live_policy:
                    semantic_differences.append(
                        {
                            "field": (
                                "semantic.mongo.collections."
                                f"{collection_name}.ttlPolicy"
                            ),
                            "snapshotValue": snapshot_policy,
                            "liveValue": live_policy,
                        }
                    )
                if snapshot_protected != live_protected:
                    semantic_differences.append(
                        {
                            "field": (
                                "semantic.mongo.collections."
                                f"{collection_name}.unexpiredDocuments"
                            ),
                            "snapshotValue": sum(snapshot_protected.values()),
                            "liveValue": sum(live_protected.values()),
                        }
                    )
            snapshot_mongo["collections"] = snapshot_collections
            live_mongo["collections"] = live_collections
            snapshot_for_generic["mongo"] = snapshot_mongo
            live_for_generic["mongo"] = live_mongo
        compare_semantic_values("semantic", snapshot_for_generic, live_for_generic)

    if semantic_unavailable:
        message = (
            "Protected continuity state could not be proven for: "
            + ", ".join(sorted(semantic_unavailable))
            + "."
        )
        (errors if strict_semantic else warnings).append(message)
    if semantic_differences:
        message = "Upgrade-protected continuity state changed between the two manifests."
        (errors if strict_semantic else warnings).append(message)

    result = {
        "schemaVersion": SCHEMA_VERSION,
        "comparedAt": iso_now(),
        "snapshotManifest": sanitize_path_label(Path(args.snapshot_manifest)),
        "liveManifest": sanitize_path_label(Path(args.live_manifest)),
        "surfaces": surfaces,
        "metadataDifferences": metadata_differences,
        "semanticDifferences": semantic_differences,
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
        previous_umask = os.umask(0o077)
        try:
            output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        finally:
            os.umask(previous_umask)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=output.parent,
            text=True,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(rendered)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.chmod(0o600)
            os.replace(temporary, output)
            output.chmod(0o600)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
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
    compare.add_argument(
        "--strict-semantic",
        action="store_true",
        help="Fail closed unless protected product-state fingerprints are present and identical.",
    )
    compare.add_argument("--output")
    return parser


def run_successor_first_upgrade_bridge(args: argparse.Namespace) -> None:
    """Let the downloaded successor validate an old shell's first upgrade.

    The predecessor invokes this successor-owned auditor after candidate activation.
    Keep the hook narrowly scoped to that post-upgrade label and suppress it for the
    bridge's own internal captures.
    """

    if os.environ.get("VIVENTIUM_FIRST_UPGRADE_BRIDGE_INTERNAL") == "1":
        return
    if not str(args.label or "").startswith("post-upgrade-"):
        return
    repo_root = Path(args.repo_root).resolve()
    app_support_dir = Path(args.app_support_dir).expanduser().resolve()
    config_file = Path(args.config_file or app_support_dir / "config.yaml").expanduser().resolve()
    runtime_dir = Path(args.runtime_dir or app_support_dir / "runtime").expanduser().resolve()
    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "viventium" / "first_upgrade_bridge.py"),
            "validate",
            "--repo-root",
            str(repo_root),
            "--app-support-dir",
            str(app_support_dir),
            "--config-file",
            str(config_file),
            "--runtime-dir",
            str(runtime_dir),
            "--lock-file",
            str(repo_root / "components.lock.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=int(
            os.environ.get(
                "VIVENTIUM_FIRST_UPGRADE_BRIDGE_TIMEOUT_SECONDS",
                "2100",
            )
        )
        + 300,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "successor validation returned no detail"
        raise SystemExit(f"First-upgrade successor validation failed: {detail}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "capture":
        run_successor_first_upgrade_bridge(args)
        return emit_json(capture_manifest(args), args.output)
    if args.command == "compare":
        return emit_json(compare_manifests(args), args.output)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
